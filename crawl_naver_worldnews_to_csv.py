"""
네이버 해외주식 뉴스 크롤링 → 기업별 CSV 저장
- 기사 목록: https://api.stock.naver.com/news/worldStock/{symbol}?page=N&pageSize=N
- 원문: Playwright로 view 페이지 렌더링 후 본문 추출

실행:
    python crawl_naver_worldnews_to_csv.py --ticker AAPL
    python crawl_naver_worldnews_to_csv.py --ticker NVDA --pages 10
"""

import csv
import json
import re
import time
import argparse
from datetime import date, datetime
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

# ─── 설정 ─────────────────────────────────────────────────────────────────────
TICKERS_PATH = "data/nasdaq100.json"
TOP_N        = 50
START_DATE   = datetime(2025, 4, 1)
OUTPUT_DIR   = f"data/naver_worldnews_20250401_{date.today().strftime('%Y%m%d')}"
DELAY_SEC    = 1.0
MAX_PAGES    = 200
PAGE_SIZE    = 20
# ──────────────────────────────────────────────────────────────────────────────

NEWS_LIST_API = "https://api.stock.naver.com/news/worldStock/{symbol}"
VIEW_URL      = "https://m.stock.naver.com/worldstock/stock/{symbol}/worldNews/view/fnGuide/{aid}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://m.stock.naver.com/",
}

FIELDNAMES = ["company", "title", "published_at", "original_url", "content"]

SYMBOL_MAP = {"BRK.B": "BRK_B.O"}

def to_naver_symbol(ticker: str) -> str:
    return SYMBOL_MAP.get(ticker, f"{ticker}.O")


def parse_dt(dt_str: str) -> tuple:
    try:
        dt = datetime.strptime(dt_str, "%Y%m%d%H%M%S")
        return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None, dt_str


def fetch_news_list(symbol: str, page: int) -> list[dict]:
    url = NEWS_LIST_API.format(symbol=symbol)
    resp = requests.get(url, params={"page": page, "pageSize": PAGE_SIZE}, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_article_content(page, url: str) -> str:
    """Playwright page 객체로 기사 원문 추출"""
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)

        # fnGuide 기사 본문 컨테이너
        el = page.query_selector(".storyContent")
        if el:
            text = el.inner_text().strip()
            if len(text) > 50:
                return re.sub(r"\n{3,}", "\n\n", text)

        return ""
    except Exception as e:
        print(f"    원문 오류: {e}")
        return ""


def crawl_ticker(ticker: str, max_pages: int = MAX_PAGES) -> list[dict]:
    symbol = to_naver_symbol(ticker)
    print(f"  심볼: {symbol}")

    # 먼저 전체 기사 목록 수집 (API)
    articles_meta = []
    seen_aids: set[str] = set()

    for page in range(1, max_pages + 1):
        try:
            items = fetch_news_list(symbol, page)
        except Exception as e:
            print(f"  [p{page}] API 오류: {e}")
            break

        if not items:
            break

        stop = False
        for item in items:
            dt_obj, pub_str = parse_dt(item.get("dt", ""))
            if dt_obj is None:
                continue
            if dt_obj < START_DATE:
                stop = True
                continue

            aid = item.get("aid", "")
            if not aid or aid in seen_aids:
                continue
            seen_aids.add(aid)

            title = item.get("tit", "").strip()
            if not title:
                continue

            articles_meta.append({
                "aid":          aid,
                "title":        title,
                "published_at": pub_str,
                "url":          VIEW_URL.format(symbol=symbol, aid=aid),
            })

        print(f"  [목록 p{page}] 누계 {len(articles_meta)}건")
        if stop:
            print(f"  {START_DATE.date()} 이전 도달, 중단")
            break
        time.sleep(0.3)

    if not articles_meta:
        return []

    print(f"  총 {len(articles_meta)}건 원문 수집 시작 (Playwright)")

    # Playwright로 원문 수집
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 390, "height": 844},
        )
        pw_page = context.new_page()

        for i, meta in enumerate(articles_meta, 1):
            print(f"  [{i}/{len(articles_meta)}] {meta['title'][:40]}")
            content = fetch_article_content(pw_page, meta["url"])

            if not content:
                print(f"    본문없음 skip")
                continue

            results.append({
                "company":      ticker,
                "title":        meta["title"],
                "published_at": meta["published_at"],
                "original_url": meta["url"],
                "content":      content,
            })
            time.sleep(DELAY_SEC)

        browser.close()

    return results


def main(only_ticker: str = None, max_pages: int = MAX_PAGES):
    with open(TICKERS_PATH, encoding="utf-8") as f:
        all_tickers = json.load(f)

    companies = [c for c in all_tickers if c["rank"] <= TOP_N]

    if only_ticker:
        companies = [c for c in companies if c["ticker"].upper() == only_ticker.upper()]
        if not companies:
            print(f"'{only_ticker}' 종목을 nasdaq100.json top50에서 찾을 수 없습니다.")
            return

    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_saved = 0

    for idx, company in enumerate(companies, 1):
        ticker = company["ticker"]
        name   = company["name"]
        print(f"\n[{idx}/{len(companies)}] {ticker} ({name}) 수집 시작")

        try:
            articles = crawl_ticker(ticker, max_pages)
        except Exception as e:
            print(f"  오류: {e}")
            articles = []

        if articles:
            safe_name = re.sub(r'[\\/:*?"<>|]', "_", ticker)
            out_path  = out_dir / f"{safe_name}.csv"
            with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(articles)
            print(f"  → {len(articles)}건 저장 완료")
        else:
            print(f"  → 수집된 기사 없음")

        total_saved += len(articles)

    print(f"\n완료: 총 {total_saved}건 → {OUTPUT_DIR}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, default=None, help="특정 티커만 수집 (예: AAPL)")
    parser.add_argument("--pages",  type=int, default=MAX_PAGES, help="종목당 최대 페이지 수")
    args = parser.parse_args()
    main(only_ticker=args.ticker, max_pages=args.pages)
