import csv
import time
from datetime import date, timedelta
from src.crawler import get_page_links, get_news_list, get_article_content

START_DATE = date(2025, 4, 1)
END_DATE   = date(2025, 12, 31)
OUTPUT     = f"data/naver_{START_DATE.strftime('%Y%m%d')}_{END_DATE.strftime('%Y%m%d')}.csv"


def iter_dates(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "source", "published_at", "original_url", "content"])
    writer.writeheader()
    total_saved = 0

    for current_date in iter_dates(START_DATE, END_DATE):
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
                    content, original_url = get_article_content(article["finance_url"])
                    if not content:
                        continue
                    writer.writerow({
                        "title": article["title"],
                        "source": article["source"],
                        "published_at": article["published_at"],
                        "original_url": original_url,
                        "content": content,
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
