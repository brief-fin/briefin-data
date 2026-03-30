"""
CSV 파일 → DB news 테이블 import
- original_url 중복 시 insert 하지 않음 (ON CONFLICT DO NOTHING)

실행:
    python import_csv_to_db.py --file data/hankyung_20250401_20260327/삼성전자.csv
    python import_csv_to_db.py --dir data/hankyung_20250401_20260327   # 폴더 전체
"""

import csv
import argparse
from datetime import datetime
from pathlib import Path

from src.db import get_connection, insert_news

DATE_FMTS = [
    "%Y.%m.%d %H:%M",
    "%Y.%m.%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
]


def parse_dt(text: str) -> datetime | None:
    for fmt in DATE_FMTS:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def import_file(conn, csv_path: Path) -> tuple[int, int]:
    """CSV 한 파일 import. (저장건수, 스킵건수) 반환"""
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    saved = skipped = 0
    for row in rows:
        title        = row.get("title", "").strip()
        original_url = row.get("original_url", "").strip()
        content      = row.get("content", "").strip()
        source       = row.get("source", "").strip()
        thumbnail    = row.get("thumbnail_url", "").strip()
        published_at = parse_dt(row.get("published_at", ""))

        if not title or not original_url:
            skipped += 1
            continue

        news_id = insert_news(
            conn,
            title=title,
            content=content,
            source=source,
            original_url=original_url,
            published_at=published_at,
            thumbnail_url=thumbnail,
        )

        if news_id:
            saved += 1
        else:
            skipped += 1  # ON CONFLICT DO NOTHING → URL 중복

    return saved, skipped


def main(file: str = None, directory: str = None):
    conn = get_connection()

    if file:
        csv_files = [Path(file)]
    elif directory:
        csv_files = sorted(Path(directory).glob("*.csv"))
    else:
        print("--file 또는 --dir 을 지정해주세요.")
        return

    total_saved = total_skipped = 0

    for csv_path in csv_files:
        print(f"\n{csv_path.name} 처리 중...")
        saved, skipped = import_file(conn, csv_path)
        print(f"  저장: {saved}건 / 스킵(중복): {skipped}건")
        total_saved   += saved
        total_skipped += skipped

    conn.close()
    print(f"\n완료 — 저장: {total_saved}건 / 스킵: {total_skipped}건")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, default=None, help="단일 CSV 파일 경로")
    parser.add_argument("--dir",  type=str, default=None, help="CSV 폴더 경로 (전체 import)")
    args = parser.parse_args()
    main(file=args.file, directory=args.dir)
