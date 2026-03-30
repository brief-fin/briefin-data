# briefin-data

뉴스 크롤링 및 데이터 수집 파이프라인

---

## 환경 셋업

### 1. 저장소 클론

```bash
git clone {repo_url}
cd briefin-data
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac / Linux
source .venv/bin/activate
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. Playwright Chromium 설치

```bash
playwright install chromium
```

> `pip install` 로 playwright 패키지는 설치되지만, 브라우저는 별도로 받아야 합니다.

### 5. 환경변수 설정

`.env` 파일을 루트에 생성 후 필요한 값 입력:

```
OPENAI_API_KEY=...
DATABASE_URL=...
```

---

## 크롤러 실행

### 국내 뉴스 (한국경제 - KOSPI200 top 50)

```bash
# 전체 수집
python crawl_hankyung_to_csv.py

# 특정 기업만
python crawl_hankyung_to_csv.py --company 삼성전자
```

결과: `data/hankyung_20250401_{오늘날짜}/`

---

### 해외 뉴스 (네이버 해외주식 - NASDAQ100 top 50)

```bash
# 전체 수집
.venv\Scripts\python crawl_naver_worldnews_to_csv.py

# 특정 종목만
.venv\Scripts\python crawl_naver_worldnews_to_csv.py --ticker AAPL

# 페이지 수 조절 (기본: 200페이지)
.venv\Scripts\python crawl_naver_worldnews_to_csv.py --ticker NVDA --pages 10
```

결과: `data/naver_worldnews_20250401_{오늘날짜}/`

> Playwright로 원문을 렌더링하므로 기사 1건당 1~2초 소요됩니다.

---

## 데이터 구조

### 종목 목록

| 파일 | 설명 |
|---|---|
| `data/kospi200_top50.json` | KOSPI200 시총 상위 50개 종목 |
| `data/nasdaq100.json` | NASDAQ100 전체 (101개, 비중 포함) |

### CSV 컬럼

| 컬럼 | 설명 |
|---|---|
| `company` | 종목명 또는 티커 |
| `title` | 기사 제목 |
| `published_at` | 발행일시 |
| `original_url` | 기사 URL |
| `content` | 기사 본문 |
