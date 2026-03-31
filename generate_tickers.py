"""
slickcharts에서 S&P 500 / Nasdaq 100 티커를 가져와 data/tickers.json에 저장.
주기적으로 실행해서 갱신하면 됨.
"""
import json
from src.tickers import get_sp500_tickers, get_nasdaq100_tickers

sp500 = get_sp500_tickers(100)
nasdaq100 = get_nasdaq100_tickers(100)

# 중복 제거 (symbol 기준) — 두 시장 모두 속한 경우 markets에 표시
combined: dict[str, dict] = {}
for item in sp500:
    combined[item["symbol"]] = {"symbol": item["symbol"], "name": item["name"], "markets": ["sp500"]}
for item in nasdaq100:
    if item["symbol"] in combined:
        combined[item["symbol"]]["markets"].append("nasdaq100")
    else:
        combined[item["symbol"]] = {"symbol": item["symbol"], "name": item["name"], "markets": ["nasdaq100"]}

output = sorted(combined.values(), key=lambda x: x["symbol"])

with open("data/tickers.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"저장 완료: {len(output)}개 티커 → data/tickers.json")
print(f"  S&P 500: {len(sp500)}개, Nasdaq 100: {len(nasdaq100)}개")
