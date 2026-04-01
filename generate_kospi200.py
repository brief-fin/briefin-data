"""
KOSPI 200 편입 종목 상위 50개 수집 → data/kospi200_top50.json 저장
출처: 네이버 금융 (https://finance.naver.com/sise/entryJongmok.naver?kospi=200)
페이지 구성: 1페이지당 10종목, 시가총액 순 정렬

실행:
    python generate_kospi200.py
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TARGET   = 50
OUT_PATH = "data/kospi200_top50.json"
BASE_URL = "https://finance.naver.com/sise/entryJongmok.naver?kospi=200&page={page}"
HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_page(page: int) -> list[dict]:
    url  = BASE_URL.format(page=page)
    resp = requests.get(url, headers=HEADERS, timeout=15)
    soup = BeautifulSoup(resp.content, "lxml", from_encoding="euc-kr")

    stocks = []
    seen   = set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        m    = re.search(r"code=(\d{6})", href)
        name = a.text.strip()
        if m and name and len(name) > 1 and m.group(1) not in seen:
            seen.add(m.group(1))
            stocks.append({"name": name, "code": m.group(1)})

    return stocks


def main():
    all_stocks: list[dict] = []
    page = 1

    while len(all_stocks) < TARGET:
        print(f"  페이지 {page} 수집 중...")
        stocks = fetch_page(page)
        if not stocks:
            print(f"  페이지 {page} 에서 데이터 없음, 종료")
            break

        all_stocks.extend(stocks)
        page += 1
        time.sleep(0.3)

    result = all_stocks[:TARGET]
    for i, s in enumerate(result, 1):
        s["rank"] = i

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n완료: {len(result)}종목 → {OUT_PATH}")
    for s in result[:10]:
        print(f"  {s['rank']:>3}. {s['name']} ({s['code']})")
    print("  ...")


if __name__ == "__main__":
    main()
