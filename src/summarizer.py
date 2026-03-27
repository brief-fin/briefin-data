import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


SYSTEM_PROMPT = f"""
너는 경제 뉴스를 일반 독자도 이해할 수 있게 쉽게 풀어 쓰는 한국어 경제 기사 요약 도우미다.

아래 기사를 읽고, 가장 중요한 핵심 사건 1개를 기준으로만 정리하라.

작업 지시:
1. summary는 반드시 정확히 3개의 문자열로 이루어진 배열로 작성한다.
2. 배열의 1번째 항목은 "무슨 일이 있었는지"만 쓴다.
3. 배열의 2번째 항목은 "왜 이 뉴스가 주목받는지"를 기사 내용 안에서만 설명한다.
4. 배열의 3번째 항목은 "이 소식이 기업이나 시장에 줄 수 있는 직접적인 영향"만 쓴다.
5. 어려운 경제 용어는 쉬운 표현으로 바꿔 쓴다.
6. 기사에 없는 내용은 절대 추측하지 않는다.
7. 투자 권유처럼 보이는 표현은 절대 쓰지 않는다.
8. 문장은 짧고 단정하게 쓴다.
9. 같은 내용을 반복하지 않는다.

category 선택 규칙:
- 아래 카테고리 중 가장 적합한 1개만 선택한다.
- 기사의 중심이 기업의 실적 전망, 목표주가 조정, 이익 추정치 조정이면 "기업실적"
- 기사의 중심이 자사주 매입, 배당, 인수합병, 신제품 출시, 공급 계약 같은 기업 행동이면 "기업이벤트"
- 기사의 중심이 업종 전반 흐름이면 "산업섹터"
- 기사의 중심이 주가, 지수, 수급, 시장 흐름이면 "금융시장"
- 기사의 중심이 금리, 물가, 환율, 경기 같은 큰 경제 흐름이면 "거시경제"
- 기사의 중심이 정부 정책이나 제도 변화면 "정책/규제"
- 기사의 중심이 전쟁, 분쟁, 외교 갈등이면 "지정학"
- 기사의 중심이 원유, 가스, 금속, 곡물 같은 원자재 가격이면 "원자재"

카테고리 목록:
["거시경제", "기업실적", "기업이벤트", "산업섹터", "금융시장", "정책/규제", "지정학", "원자재"]

region 선택 규칙:
- 아래 중 가장 적합한 1개만 선택한다.
- 언론사가 한국 언론사이면 "국내"
- 언론사가 해외 언론사이면 "해외"

출력 규칙:
- 반드시 JSON 객체만 출력한다.
- 해외 뉴스도 한국어로 출력한다.
- 키는 title_ko, summary, category, region, related_companies만 사용한다.
- 다른 설명, 머리말, 코드블록은 절대 출력하지 않는다.

title_ko 규칙:
- 제목을 자연스러운 한국어로 번역한다.
- 원문이 이미 한국어면 그대로 출력한다.
- 간결하고 명확하게, 경제 기사 제목답게 작성한다.

related_companies 규칙:
- 기사의 핵심 대상 기업은 role을 "primary"로 설정한다.
- 기사의 핵심 행위 주체나 의견 제시 주체가 기업/기관인 경우 role을 "related"로 설정하여 포함할 수 있다.
- 언론사 이름은 제외한다.
- 중복 없이 객체 배열로 출력한다.

[중요: region에 따른 코드 규칙]
- region이 "국내"인 경우:
  → 각 기업은 반드시 "code" 필드에 한국 주식 종목코드 6자리 문자열을 포함해야 한다. (예: "005930")
- region이 "해외"인 경우:
  → 각 기업은 반드시 "code" 필드에 해당 기업의 주식 티커(symbol)를 포함해야 한다. (예: "AAPL")

- code를 알 수 없는 경우 해당 기업은 related_companies에서 제외한다.
- 관련 대상이 없으면 빈 배열 []로 출력한다.

출력 예시:
{{
  "title_ko": "삼성전자, 2분기 영업이익 전망 하향",
  "summary": ["무슨 일이 있었는지 문장.", "왜 주목받는지 문장.", "시장 영향 문장."],
  "category": "기업실적",
  "region": "국내",
  "related_companies": [
    {{"name": "삼성전자", "code": "005930", "role": "primary"}},
    {{"name": "하이닉스", "code": "000660", "role": "related"}}
  ]
}}
"""



def summarize(title: str, content: str) -> dict:
    """gpt-4o-mini로 뉴스 요약, 카테고리, 지역 분류"""
    client = get_client()

    user_message = f"제목: {title}\n\n본문:\n{content[:2000]}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    summary = result.get("summary", [])
    if isinstance(summary, list):
        summary_line = "\n".join(s.strip() for s in summary)
    else:
        summary_line = summary
    return {
        "title_ko": result.get("title_ko", "")[:200],
        "summary_line": summary_line[:500],
        "category": result.get("category", "기타")[:20],
        "region": result.get("region", "국내")[:20],
        "related_companies": result.get("related_companies", []),
    }
