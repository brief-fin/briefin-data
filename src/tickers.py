import re
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def get_sp500_tickers(limit: int = 100) -> list[dict]:
    """slickcharts S&P 500에서 {symbol, name} 목록 반환"""
    resp = requests.get("https://www.slickcharts.com/sp500", headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    results = []
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        name_a = cells[1].find("a")
        symbol_a = cells[2].find("a")
        if name_a and symbol_a:
            results.append({
                "symbol": symbol_a.text.strip(),
                "name": name_a.text.strip(),
            })
        if len(results) >= limit:
            break

    return results


def get_nasdaq100_tickers(limit: int = 100) -> list[dict]:
    """slickcharts Nasdaq 100에서 {symbol, name} 목록 반환 (SvelteKit 스크립트 파싱)"""
    resp = requests.get("https://www.slickcharts.com/nasdaq100", headers=HEADERS)
    resp.raise_for_status()

    match = re.search(r"nasdaq100List:\s*(\[.*?\])\s*[,}]", resp.text, re.DOTALL)
    if not match:
        raise ValueError("nasdaq100List를 페이지에서 찾을 수 없습니다")

    raw = match.group(1)
    # JS 객체 키를 JSON 형식으로 변환 (symbol:"NVDA" → "symbol":"NVDA")
    raw = re.sub(r'([{,])\s*(\w+):', r'\1"\2":', raw)
    # JS 소수점 표기 수정 (-.807 → -0.807)
    raw = re.sub(r'([-+]?)\.(\d)', lambda m: f'{m.group(1) or ""}0.{m.group(2)}', raw)

    data = json.loads(raw)
    sorted_data = sorted(data, key=lambda x: x["rank"])
    return [{"symbol": e["symbol"], "name": e["name"]} for e in sorted_data[:limit]]
