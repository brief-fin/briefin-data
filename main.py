import argparse
from src.pipeline import run as run_pipeline, backfill_embed as run_backfill, backfill_summarize as run_backfill_summarize, backfill_companies as run_backfill_companies

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="briefin 뉴스 파이프라인")
    parser.add_argument("--backfill", action="store_true", help="요약 없는 기사 GPT 요약 + 임베딩 처리")
    parser.add_argument("--backfill-embed", action="store_true", help="요약은 있지만 임베딩 없는 기사 임베딩 처리")
    parser.add_argument("--backfill-companies", action="store_true", help="관련기업 없는 기사(한국경제 제외) GPT 분류 처리")
    parser.add_argument("--pages", type=int, default=1, help="크롤링 페이지 수 (기본: 1)")
    parser.add_argument("--date", type=str, default=None, help="크롤링 날짜 (YYYY-MM-DD, 기본: 오늘)")
    parser.add_argument("--limit", type=int, default=None, help="처리할 뉴스 최대 개수 (기본: 제한 없음)")
    parser.add_argument("--offset", type=int, default=0, help="처리 시작 위치 (기본: 0)")
    args = parser.parse_args()

    if args.backfill:
        run_backfill_summarize()
    elif args.backfill_embed:
        run_backfill(limit=args.limit, offset=args.offset)
    elif args.backfill_companies:
        run_backfill_companies(limit=args.limit, offset=args.offset)
    else:
        run_pipeline(max_pages=args.pages, limit=args.limit, date=args.date)
