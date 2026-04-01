"""
매 정각 크롤링 스케줄러
- 한국경제: KOSPI200 top50 기업별 최근 기사 수집
- 네이버 금융 메인뉴스: 당일 기사 수집
- 수집 즉시 임베딩 + 요약 후 DB insert, 중복 URL은 자동 skip
"""

import json
import re
import time
import logging
from datetime import datetime, timedelta

from urllib.parse import quote
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler

from src.crawler import get_page_links, get_news_list, get_article_content
from src.db import get_connection, insert_news, insert_news_embedding, insert_news_summary, insert_news_companies
from src.embedder import embed
from src.summarizer import summarize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ─── 설정 ─────────────────────────────────────────────────────────────────────
LOOKBACK_HOURS = 1        # 최근 N시간 이내 기사만 수집
HANKYUNG_PAGES = 2        # 한경 태그 페이지당 약 15건, 2페이지 = 30건
DELAY_SEC      = 2.0      # 요청 간격 (초)
# ──────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


# ─── 공통: 임베딩 + 요약 후 DB 저장 ────────────────────────────────────────────

def process_and_save(conn, title, content, source, original_url, published_at, thumbnail_url="") -> bool:
    """news insert → 요약 → 임베딩(summary_line 기준) 순으로 처리. 신규 저장이면 True 반환."""
    news_id = insert_news(
        conn,
        title=title,
        content=content,
        source=source,
        original_url=original_url,
        published_at=published_at,
        thumbnail_url=thumbnail_url,
    )
    if not news_id:
        return False  # URL 중복 skip

    try:
        result = summarize(title, content)
        related_companies = result.pop("related_companies", [])
        insert_news_summary(conn, news_id, **result)
        insert_news_companies(conn, news_id, related_companies)
    except Exception as e:
        log.warning(f"요약 오류 ({title[:30]}): {e}")
        return True

    try:
        embedding = embed(result["summary_line"])
        insert_news_embedding(conn, news_id, embedding)
    except Exception as e:
        log.warning(f"임베딩 오류 ({title[:30]}): {e}")

    return True


# ─── 한경 ──────────────────────────────────────────────────────────────────────

def crawl_hankyung(conn, cutoff):
    with open("data/kospi200_top50.json", encoding="utf-8") as f:
        companies = json.load(f)

    date_fmts = ["%Y.%m.%d %H:%M", "%Y.%m.%d", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
    saved = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx     = browser.new_context(user_agent=HEADERS["User-Agent"])
        pw_page = ctx.new_page()

        for company in companies:
            name = company["name"]
            for page in range(1, HANKYUNG_PAGES + 1):
                try:
                    url = f"https://www.hankyung.com/tag/{quote(name)}?page={page}"
                    pw_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    soup = BeautifulSoup(pw_page.content(), "lxml")

                    stop = False
                    for card in soup.select("div.text-cont"):
                        a       = card.select_one("h2.news-tit a[href*='hankyung.com/article']")
                        date_el = card.select_one("p.txt-date")
                        if not a or not date_el:
                            continue

                        pub_str = date_el.text.strip()
                        pub_dt  = None
                        for fmt in date_fmts:
                            try:
                                pub_dt = datetime.strptime(pub_str, fmt)
                                break
                            except ValueError:
                                continue

                        if pub_dt and pub_dt <= cutoff:
                            stop = True
                            break

                        article_url = a["href"]
                        title       = a.text.strip()

                        try:
                            pw_page.goto(article_url, wait_until="domcontentloaded", timeout=30000)
                            soup2 = BeautifulSoup(pw_page.content(), "lxml")

                            og = soup2.select_one('meta[property="og:image"]')
                            thumbnail = og["content"] if og and og.get("content") else ""

                            article = soup2.select_one("#articletxt")
                            if not article:
                                for sel in [".article-body", "#article-body", ".content-text", "article"]:
                                    article = soup2.select_one(sel)
                                    if article:
                                        break
                            if not article:
                                continue
                            for tag in article.select("script, style, figure, .ad"):
                                tag.decompose()
                            content = re.sub(r"\n{3,}", "\n\n", article.get_text(separator="\n", strip=True)).strip()

                            if process_and_save(conn, title, content, "한국경제", article_url, pub_dt, thumbnail):
                                saved += 1
                            time.sleep(DELAY_SEC)
                        except Exception as e:
                            log.warning(f"[한경] 본문 오류 {title[:30]}: {e}")

                    if stop:
                        break

                except Exception as e:
                    log.warning(f"[한경] {name} p{page} 오류: {e}")
                    break

        browser.close()

    log.info(f"[한경] 완료 — {saved}건 신규 저장")


# ─── 네이버 금융 메인뉴스 ────────────────────────────────────────────────────────

def crawl_naver_mainnews(conn, cutoff):
    today = datetime.now().strftime("%Y-%m-%d")
    saved = 0

    try:
        page_links = get_page_links(today)
        articles_meta = get_news_list(page_links)
    except Exception as e:
        log.warning(f"[네이버] 목록 수집 오류: {e}")
        return

    for article in articles_meta:
        pub_dt = article.get("published_at")
        if pub_dt and pub_dt <= cutoff:
            continue

        try:
            content, original_url, thumbnail_url = get_article_content(article["finance_url"])
            if not content:
                continue

            if process_and_save(conn, article["title"], content, article["source"], original_url, pub_dt, thumbnail_url):
                saved += 1
            time.sleep(DELAY_SEC)
        except Exception as e:
            log.warning(f"[네이버] 본문 오류 {article['title'][:30]}: {e}")

    log.info(f"[네이버] 완료 — {saved}건 신규 저장")


# ─── 스케줄러 ──────────────────────────────────────────────────────────────────

def run_all():
    log.info("=== 크롤링 시작 ===")
    conn = get_connection()
    try:
        cutoff = datetime.now() - timedelta(hours=LOOKBACK_HOURS)
        log.info(f"cutoff: {cutoff} (최근 {LOOKBACK_HOURS}시간)")

        crawl_hankyung(conn, cutoff)
        crawl_naver_mainnews(conn, cutoff)
    except Exception as e:
        log.error(f"크롤링 오류: {e}")
    finally:
        conn.close()
    log.info("=== 크롤링 완료 ===")


if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(run_all, "cron", minute=0)  # 매 정각
    log.info("스케줄러 시작 — 매 정각 실행")

    # 시작 시 즉시 1회 실행
    run_all()
    scheduler.start()
