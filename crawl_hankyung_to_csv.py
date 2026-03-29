"""
한국경제 태그 페이지 크롤링 → 기업별 CSV 저장
https://www.hankyung.com/tag/{기업명} 에서 2025-04-01 ~ 오늘까지 기사 수집

실행:
    python crawl_hankyung_to_csv.py
"""

import csv
import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# ─── 설정 ─────────────────────────────────────────────────────────────────────
TICKERS_PATH = "data/kospi200_top50.json"
START_DATE   = datetime(2025, 4, 1)
OUTPUT_DIR   = f"data/hankyung_20250401_{date.today().strftime('%Y%m%d')}"
DELAY_SEC    = 0.5
# ──────────────────────────────────────────────────────────────────────────────

TAG_URL = "https://www.hankyung.com/tag/{tag}?page={page}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
FIELDNAMES = ["company", "title", "published_at", "original_url", "content"]
DATE_FMTS  = ["%Y.%m.%d %H:%M", "%Y.%m.%d", "%Y-%m-%d %H:%M", "%Y-%m-%d"]


def parse_date(text: str) -> datetime | None:
    for fmt in DATE_FMTS:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def get_tag_page(tag: str, page: int) -> list[dict]:
    """태그 페이지에서 기사 목록 반환"""
    url  = TAG_URL.format(tag=quote(tag), page=page)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "lxml", from_encoding="utf-8")

    articles = []
    for card in soup.select("div.text-cont"):
        a        = card.select_one("h2.news-tit a[href*='hankyung.com/article']")
        date_el  = card.select_one("p.txt-date")
        if not a or not date_el:
            continue

        title        = a.text.strip()
        article_url  = a["href"]
        published_at = date_el.text.strip()

        if title and article_url:
            articles.append({
                "title":        title,
                "url":          article_url,
                "published_at": published_at,
                "dt":           parse_date(published_at),
            })

    return articles


def get_article_content(url: str) -> str:
    """기사 본문 추출"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml", from_encoding="utf-8")

        article = soup.select_one("#articletxt")
        if not article:
            for sel in [".article-body", "#article-body", ".content-text", "article"]:
                article = soup.select_one(sel)
                if article:
                    break
        if not article:
            return ""

        for tag in article.select("script, style, figure, .ad"):
            tag.decompose()

        return re.sub(r"\n{3,}", "\n\n", article.get_text(separator="\n", strip=True)).strip()
    except Exception:
        return ""


def crawl_company(company_name: str) -> list[dict]:
    """기업 태그 페이지를 순회하며 START_DATE 이후 기사 전부 수집"""
    results    = []
    seen_urls: set[str] = set()
    page       = 1

    while True:
        try:
            articles = get_tag_page(company_name, page)
        except Exception as e:
            print(f"  [p{page}] 오류: {e}")
            break

        if not articles:
            break

        stop = False
        for item in articles:
            dt = item["dt"]

            # START_DATE 이전이면 더 이상 수집 불필요
            if dt and dt < START_DATE:
                stop = True
                continue

            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

            content = get_article_content(url)
            if not content:
                print(f"  본문없음 skip: {item['title'][:40]}")
                continue

            results.append({
                "company":      company_name,
                "title":        item["title"],
                "published_at": item["published_at"],
                "original_url": url,
                "content":      content,
            })
            time.sleep(DELAY_SEC)

        print(f"  [p{page}] 누계 {len(results)}건")

        if stop:
            break

        page += 1
        time.sleep(DELAY_SEC)

    return results


def main(only: str = None):
    with open(TICKERS_PATH, encoding="utf-8") as f:
        companies = json.load(f)

    if only:
        companies = [c for c in companies if c["name"] == only]
        if not companies:
            print(f"'{only}' 기업을 kospi200_top50.json에서 찾을 수 없습니다.")
            return

    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    total_saved = 0

    for idx, company in enumerate(companies, 1):
        name = company["name"]
        print(f"\n[{idx}/{len(companies)}] {name} 수집 시작")

        try:
            articles = crawl_company(name)
        except Exception as e:
            print(f"  오류: {e}")
            articles = []

        if articles:
            safe_name = re.sub(r'[\\/:*?"<>|]', "_", name)
            out_path  = out_dir / f"{safe_name}.csv"
            with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
                writer.writeheader()
                writer.writerows(articles)

        print(f"  → {len(articles)}건 저장 (누계 {total_saved + len(articles)}건)")
        total_saved += len(articles)

    print(f"\n완료: 총 {total_saved}건 → {OUTPUT_DIR}/")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", type=str, default=None, help="특정 기업명만 수집 (예: SK하이닉스)")
    args = parser.parse_args()
    main(only=args.company)
