from datetime import datetime, timedelta, timezone
from src.crawler import crawl
from src.embedder import embed
from src.summarizer import summarize, classify_only, extract_summary_sumy
from src import db

RECENT_DAYS = 14


def backfill_summarize():
    """news_summaries가 없는 기사 처리.
    최근 2주: GPT 풀 요약
    2주 이전: sumy 요약 + GPT 분류(category/region/ticker)만
    """
    conn = db.get_connection()

    articles = db.fetch_unsummarized_news(conn)
    print(f"[backfill] 요약 대상: {len(articles)}건")

    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)
    done = 0
    for article in articles:
        title = article["title"]
        content = article["content"] or ""
        published_at = article["published_at"]

        # timezone 처리
        if published_at and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)

        is_naver = "news.naver.com" in article.get("original_url", "")
        is_hankyung = "hankyung.com" in article.get("original_url", "")
        is_recent = published_at is not None and published_at >= cutoff

        try:
            if is_recent and is_naver:
                result = summarize(title, content)
                summary_line = result.pop("summary_line")
                related_companies = result.pop("related_companies", [])
                category = result["category"]
                region = result["region"]
            else:
                summary_line = extract_summary_sumy(content)
                if not summary_line:
                    print(f"[backfill] skip (본문 없음, id: {article['id']})")
                    continue
                classified = classify_only(title, content)
                category = classified["category"]
                region = classified["region"]
                related_companies = classified.get("related_companies", []) if not is_hankyung else []
        except Exception as e:
            print(f"[backfill] 오류 (id: {article['id']}): {e}")
            continue

        db.insert_news_summary(conn, article["id"], summary_line, category, region)
        if not is_hankyung:
            db.insert_news_companies(conn, article["id"], related_companies)

        try:
            embedding = embed(summary_line)
            db.insert_news_embedding(conn, article["id"], embedding)
        except Exception as e:
            print(f"[backfill] 임베딩 오류 (id: {article['id']}): {e}")

        done += 1
        mode = "GPT" if (is_recent and is_naver) else "sumy"
        print(f"[backfill] {done}/{len(articles)} ({mode}) 완료: {title[:40]}")

    conn.close()
    print(f"\n[backfill] 완료 — {done}건 요약")


def backfill_companies():
    """news_companies가 없는 뉴스(한국경제 제외)에 GPT로 category, 관련기업 추출 후 저장"""
    conn = db.get_connection()

    articles = db.fetch_news_without_companies(conn)
    print(f"[backfill_companies] 대상: {len(articles)}건")

    done = 0
    for article in articles:
        try:
            result = classify_only(article["title"], article["content"] or "")
        except Exception as e:
            print(f"[backfill_companies] 오류 (id: {article['id']}): {e}")
            continue

        db.insert_news_companies(conn, article["id"], result["related_companies"])
        db.update_news_summary_category(conn, article["id"], result["category"])

        done += 1
        print(f"[backfill_companies] {done}/{len(articles)} 완료: {article['title'][:40]}")
        print(f"  category : {result['category']}")
        print(f"  companies: {result['related_companies']}")

    conn.close()
    print(f"\n[backfill_companies] 완료 — {done}건 처리")


def backfill_embed():
    """news_summaries는 있지만 news_embeddings가 없는 기사들을 summary_line으로 임베딩"""
    conn = db.get_connection()

    unembedded = db.fetch_unembedded_news(conn)
    print(f"[backfill] 임베딩 대상: {len(unembedded)}건")

    done = 0
    for article in unembedded:
        try:
            embedding = embed(article["summary_line"])
            db.insert_news_embedding(conn, article["id"], embedding)
            done += 1
            print(f"[backfill] {done}/{len(unembedded)} 완료 (id: {article['id']})")
        except Exception as e:
            print(f"[backfill] 오류 (id: {article['id']}): {e}")

    conn.close()
    print(f"\n[backfill] 완료 — {done}건 임베딩")


def run(max_pages: int = None, limit: int = None, date: str = None):
    conn = db.get_connection()

    print(f"[pipeline] 네이버 경제 뉴스 크롤링 시작 ({max_pages}페이지)")
    articles = crawl(max_pages=max_pages, date=date)
    if limit:
        articles = articles[:limit]
    print(f"[pipeline] 크롤링 완료: {len(articles)}건")

    # 1단계: news 저장
    staged = []  # (news_id, article)
    for article in articles:
        original_url = article["original_url"]
        content = article.get("content", "")

        if db.news_exists(conn, original_url):
            print(f"[pipeline] skip (URL 중복): {article['title'][:30]}")
            continue

        news_id = db.insert_news(
            conn,
            title=article["title"],
            content=content,
            source=article["source"],
            original_url=original_url,
            published_at=article["published_at"],
            thumbnail_url=article.get("thumbnail_url", ""),
        )
        if not news_id:
            continue

        staged.append((news_id, article))
        print(f"[pipeline] 수집 완료: {article['title'][:40]}")

    print(f"\n[pipeline] 수집 완료 — {len(staged)}건, 요약 시작")

    # 2단계: GPT 요약 → summary_line 임베딩 → news_embeddings 저장
    saved = 0
    for news_id, article in staged:
        try:
            summary = summarize(article["title"], article.get("content", ""))
        except Exception as e:
            print(f"[pipeline] 요약 오류: {e}")
            continue

        related_companies = summary.pop("related_companies", [])
        summary.pop("title_ko", None)
        db.insert_news_summary(conn, news_id, **summary)
        db.insert_news_companies(conn, news_id, related_companies)

        try:
            embedding = embed(summary["summary_line"])
            db.insert_news_embedding(conn, news_id, embedding)
        except Exception as e:
            print(f"[pipeline] 임베딩 오류: {e}")

        saved += 1
        print(f"[pipeline] 요약 완료: {article['title'][:40]}")

    conn.close()
    print(f"\n[pipeline] 완료 — 수집 {len(staged)}건 / 요약 {saved}건")
