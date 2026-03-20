import argparse
from src.pipeline import run as run_pipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="briefin 뉴스 파이프라인")
    parser.add_argument("--pages", type=int, default=1, help="크롤링 페이지 수 (기본: 3)")
    parser.add_argument("--limit", type=int, default=None, help="처리할 뉴스 최대 개수 (기본: 제한 없음)")
    parser.add_argument("--date", type=str, default=None, help="크롤링 날짜 (YYYY-MM-DD, 기본: 오늘)")
    args = parser.parse_args()

    run_pipeline(max_pages=args.pages, limit=args.limit, date=args.date)
