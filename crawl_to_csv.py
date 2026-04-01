"""
네이버 금융 메인뉴스 크롤링 → CSV 저장

실행:
    python crawl_to_csv.py
    python crawl_to_csv.py --resume-from 2025-10-19   # 중단된 날짜부터 재시작
"""

import csv
import time
import argparse
from datetime import date, datetime, timedelta
from src.crawler import get_page_links, get_news_list, get_article_content

START_DATE = date(2025, 10, 15)
END_DATE   = date(2025, 12, 31)
OUTPUT     = f"data/naver_{START_DATE.strftime('%Y%m%d')}_{END_DATE.strftime('%Y%m%d')}.csv"

FIELDNAMES = ["title", "source", "published_at", "original_url", "content", "thumbnail_url"]

MAX_RETRIES = 3
RETRY_DELAY = 5  # 재시도 대기 (초)


def iter_dates(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def fetch_with_retry(finance_url: str):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return get_article_content(finance_url)
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            print(f"  재시도 {attempt}/{MAX_RETRIES - 1} ({e.__class__.__name__})")
            time.sleep(RETRY_DELAY * attempt)


def main(resume_from: str = None):
    start = START_DATE
    if resume_from:
        start = datetime.strptime(resume_from, "%Y-%m-%d").date()
        print(f"[재시작] {start}부터 수집")

    # resume_from이 있으면 append 모드, 없으면 새 파일
    mode = "a" if resume_from else "w"

    with open(OUTPUT, mode, newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if mode == "w":
            writer.writeheader()

        total_saved = 0

        for current_date in iter_dates(start, END_DATE):
            date_str = current_date.strftime("%Y-%m-%d")
            print(f"\n[{date_str}] 수집 시작")

            try:
                page_links = get_page_links(date_str)
                print(f"  페이지: {len(page_links)}개")

                articles = get_news_list(page_links)
                print(f"  기사 목록: {len(articles)}건")

                saved = 0
                for i, article in enumerate(articles, 1):
                    try:
                        content, original_url, thumbnail_url = fetch_with_retry(article["finance_url"])
                        if not content:
                            continue
                        writer.writerow({
                            "title":         article["title"],
                            "source":        article["source"],
                            "published_at":  article["published_at"],
                            "original_url":  original_url,
                            "content":       content,
                            "thumbnail_url": thumbnail_url,
                        })
                        f.flush()
                        saved += 1
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"  [{i}] 오류: {e}")

                total_saved += saved
                print(f"  저장: {saved}건 (누계 {total_saved}건)")

            except Exception as e:
                print(f"  [{date_str}] 날짜 전체 오류: {e}")

    print(f"\n완료: 총 {total_saved}건 → {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-from", type=str, default=None,
                        help="중단된 날짜부터 재시작 (예: 2025-10-19)")
    args = parser.parse_args()
    main(resume_from=args.resume_from)
