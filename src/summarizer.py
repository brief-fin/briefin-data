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
    1. summary는 반드시 정확히 3문장으로 작성한다.
    2. 1문장째는 "무슨 일이 있었는지"만 쓴다.
    3. 2문장째는 "왜 이 뉴스가 주목받는지"를 기사 내용 안에서만 설명한다.
    4. 3문장째는 "이 소식이 기업이나 시장에 줄 수 있는 직접적인 영향"만 쓴다.
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
    - 국내, 미국, 중국, 유럽, 글로벌, 기타

    출력 규칙:
    - 반드시 JSON 객체만 출력한다.
    - 키는 summary, category, region, related_companies만 사용한다.
    - 다른 설명, 머리말, 코드블록은 절대 출력하지 않는다.

    related_companies 규칙:
    - 기사의 핵심 대상 기업은 반드시 포함한다.
    - 기사의 핵심 행위 주체나 의견 제시 주체가 기업/기관인 경우 함께 포함할 수 있다.
    - 언론사 이름은 제외한다.
    - 중복 없이 배열로 출력한다.
    - 관련 대상이 없으면 빈 배열 []로 출력한다.

    출력 예시:
    {{
    "summary": "문장1. 문장2. 문장3.",
    "category": "기업실적",
    "region": "국내",
    "related_companies": ["기업1", "기업2"]
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
    return {
        "summary_line": result.get("summary", "")[:500],
        "category": result.get("category", "기타")[:20],
        "region": result.get("region", "국내")[:20],
        "related_companies": result.get("related_companies", []),
    }
