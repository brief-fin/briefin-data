import argparse
from src.pipeline import run as run_pipeline
from src.foreign_pipeline import run as run_foreign_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="briefin 뉴스 파이프라인")
    parser.add_argument("--overseas", action="store_true", help="해외 뉴스 수집 모드")
    parser.add_argument("--pages", type=int, default=1, help="[국내] 크롤링 페이지 수 (기본: 1)")
    parser.add_argument("--date", type=str, default=None, help="[국내] 크롤링 날짜 (YYYY-MM-DD, 기본: 오늘)")
    parser.add_argument("--limit", type=int, default=None, help="처리할 뉴스 최대 개수 (기본: 제한 없음)")
    parser.add_argument("--max-news", type=int, default=5, help="[해외] 티커당 최대 뉴스 수 (기본: 5)")
    args = parser.parse_args()

    if args.overseas:
        run_foreign_pipeline(limit=args.limit, max_news_per_ticker=args.max_news)
    else:
        run_pipeline(max_pages=args.pages, limit=args.limit, date=args.date)
