import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

_sumy_summarizer = LexRankSummarizer(Stemmer("Korean"))
_sumy_summarizer.stop_words = get_stop_words("Korean")

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
2. 1문장째는 "무슨 일이 있었는지"만 쓴다. (각 문장은 50자 이내로 쓴다.)
3. 2문장째는 기사 내용 안에서 이 사건의 배경이나 원인을 쓴다. 배경/원인이 없으면 이 뉴스가 중요한 이유나 관련 맥락을 쓴다.
4. 3문장째는 기사에 명시된 영향이나 전망만 쓴다. 기사에 없는 내용은 절대 쓰지 않는다.
5. 각 문장은 반드시 줄바꿈(\\n)으로 구분한다. 예: "문장1.\\n문장2.\\n문장3."
6. 어려운 경제 용어는 쉬운 표현으로 바꿔 쓴다.
7. 기사에 없는 내용은 절대 추측하지 않는다.
8. 투자 권유처럼 보이는 표현은 절대 쓰지 않는다.
9. 문장은 짧고 단정하게 쓴다.
10. 같은 내용을 반복하지 않는다.
11. 기업명, 제품명, 수치(금액, 비율, 날짜 등)는 원문 그대로 사용한다.

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
- 키는 summary, category, region, related_companies만 사용한다.
- 다른 설명, 머리말, 코드블록은 절대 출력하지 않는다.

 related_companies 규칙:
- 기사의 핵심 주제가 되는 기업만 추출한다. 배경, 비교, 업계 사례로 언급된 기업은 포함하지 않는다.
- 기사 제목에 등장하거나, 기사 전체가 해당 기업의 행동/실적/이슈를 다루는 경우에만 포함한다.
- 최대 2개까지만 포함한다.
- 국내 종목은 6자리 숫자만 허용 (예: "005930"), 해외 종목은 알파벳만 허용 (예: "AAPL")
- ticker를 정확히 모르는 기업은 절대 포함하지 않는다.
- 언론사 ticker는 제외한다.
- 중복 없이 배열로 출력한다.
- 해당 기업이 없으면 빈 배열 []로 출력한다.

출력 예시:
{{
"summary": "문장1.\n문장2.\n문장3.",
"category": "기업실적",
"region": "국내",
"related_companies": ["005930", "000660"]
}}
"""


CLASSIFY_PROMPT = """
    너는 경제 뉴스를 분류하는 도우미다.

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

    related_companies 규칙:
    - 기사의 핵심 주제가 되는 기업만 추출한다. 배경, 비교, 업계 사례로 언급된 기업은 포함하지 않는다.
    - 기사 제목에 등장하거나, 기사 전체가 해당 기업의 행동/실적/이슈를 다루는 경우에만 포함한다.
    - 최대 2개까지만 포함한다.
    - 국내 종목은 6자리 숫자만 허용 (예: "005930"), 해외 종목은 알파벳만 허용 (예: "AAPL")
    - ticker를 정확히 모르는 기업은 절대 포함하지 않는다.
    - 언론사 ticker는 제외한다.
    - 중복 없이 배열로 출력한다.
    - 해당 기업이 없으면 빈 배열 []로 출력한다.

    출력 규칙:
    - 반드시 JSON 객체만 출력한다.
    - 키는 category, region, related_companies만 사용한다.
    - 다른 설명, 머리말, 코드블록은 절대 출력하지 않는다.

    출력 예시:
    {
    "category": "기업실적",
    "region": "국내",
    "related_companies": ["005930", "000660"]
    }
    """


def extract_summary_sumy(content: str, sentence_count: int = 3) -> str:
    """sumy LexRank로 핵심 문장 추출"""
    if not content or not content.strip():
        return ""

    parser = PlaintextParser.from_string(content, Tokenizer("korean"))
    result = _sumy_summarizer(parser.document, sentence_count)
    print(len(result), result)
    return "\n".join(str(s) for s in result)


def classify_only(title: str, content: str) -> dict:
    """gpt-4o-mini로 category, region, ticker만 분류 (summary 생성 없음)"""
    client = get_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": CLASSIFY_PROMPT},
            {"role": "user", "content": f"제목: {title}\n\n본문:\n{content[:3000]}"},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    return {
        "category": result.get("category", "거시경제")[:20],
        "region": result.get("region", "국내")[:20],
        "related_companies": result.get("related_companies", []),
    }


def summarize(title: str, content: str) -> dict:
    """gpt-4o-mini로 뉴스 요약, 카테고리, 지역 분류"""
    client = get_client()

    user_message = f"제목: {title}\n\n본문:\n{content[:6000]}"

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
        "category": result.get("category", "거시경제")[:20],
        "region": result.get("region", "국내")[:20],
        "related_companies": result.get("related_companies", []),
    }
