from src.crawler import crawl
from src.embedder import embed
from src.summarizer import summarize
from src import db

SIMILARITY_THRESHOLD = 0.7


def run(max_pages: int = None, limit: int = None, date: str = None):
    conn = db.get_connection()

    print(f"[pipeline] 네이버 경제 뉴스 크롤링 시작 ({max_pages}페이지)")
    articles = crawl(max_pages=max_pages, date=date)
    if limit:
        articles = articles[:limit]
    print(f"[pipeline] 크롤링 완료: {len(articles)}건")

    saved = 0
    for article in articles:
        original_url = article["original_url"]
        content = article.get("content", "")

        if db.news_exists(conn, original_url):
            print(f"[pipeline] skip (URL 중복): {article['title'][:30]}")
            continue

        try:
            embedding = embed(article["title"] + " " + content)
        except Exception as e:
            print(f"[pipeline] 임베딩 오류: {e}")
            continue

        is_similar, similar_title = db.is_similar_to_recent(conn, embedding, hours=3, threshold=SIMILARITY_THRESHOLD)
        if is_similar:
            print(f"[pipeline] skip (유사 뉴스): {article['title'][:30]}")
            print(f"           └ 유사 기사: {similar_title}")
            continue

        try:
            summary = summarize(article["title"], content)
        except Exception as e:
            print(f"[pipeline] 요약 오류: {e}")
            continue

        news_id = db.insert_news(
            conn,
            title=article["title"],
            content=content,
            source=article["source"],
            original_url=original_url,
            published_at=article["published_at"],
        )
        if not news_id:
            continue

        db.insert_news_embedding(conn, news_id, embedding)
        related_companies = summary.pop("related_companies", [])
        summary.pop("title_ko", None)
        db.insert_news_summary(conn, news_id, **summary)

        saved += 1
        print(f"[pipeline] 저장 완료: {article['title'][:40]}")

    conn.close()
    print(f"\n[pipeline] 완료 — {saved}건 저장")
