"""
기존 한경 CSV에 thumbnail_url 컬럼 추가
original_url에서 og:image 메타태그를 가져와 덮어씀

실행:
    python add_thumbnail_hankyung.py
    python add_thumbnail_hankyung.py --dir data/hankyung_20250401_20260328
"""

import csv
import time
import argparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TARGET_DIR = "data/hankyung_20250401_20260328"
DELAY_SEC  = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

OLD_FIELDS = ["company", "title", "published_at", "original_url", "content"]
NEW_FIELDS = ["company", "title", "published_at", "original_url", "content", "source", "thumbnail_url"]


def fetch_thumbnail(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml", from_encoding="utf-8")
        og = soup.select_one('meta[property="og:image"]')
        return og["content"] if og and og.get("content") else ""
    except Exception:
        return ""


def process_file(csv_path: Path):
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"  비어있음, skip")
        return

    # 이미 thumbnail_url 컬럼이 있으면 skip
    if "thumbnail_url" in rows[0]:
        print(f"  이미 thumbnail_url 있음, skip")
        return

    updated = []
    for i, row in enumerate(rows, 1):
        url = row.get("original_url", "")
        thumbnail = fetch_thumbnail(url) if url else ""
        print(f"  [{i}/{len(rows)}] {'있음' if thumbnail else '없음'} {url[:60]}")
        updated.append({
            **row,
            "source":        "한국경제",
            "thumbnail_url": thumbnail,
        })
        time.sleep(DELAY_SEC)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=NEW_FIELDS)
        writer.writeheader()
        writer.writerows(updated)

    print(f"  → 저장 완료 ({len(updated)}건)")


def main(target_dir: str = TARGET_DIR):
    csv_files = sorted(Path(target_dir).glob("*.csv"))
    print(f"대상 폴더: {target_dir} ({len(csv_files)}개 파일)")

    for idx, csv_path in enumerate(csv_files, 1):
        print(f"\n[{idx}/{len(csv_files)}] {csv_path.name}")
        process_file(csv_path)

    print("\n완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, default=TARGET_DIR)
    args = parser.parse_args()
    main(args.dir)
