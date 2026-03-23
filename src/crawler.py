import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

ROOT_URL = "https://finance.naver.com"
MAIN_URL = "https://finance.naver.com/news/mainnews.nhn?date="


def get_page_links(date: str) -> list[str]:
    """날짜별 페이지 링크 목록 반환"""
    resp = requests.get(MAIN_URL + date, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    navi = soup.find("table", {"class": "Nnavi"})
    if not navi:
        return [f"/news/mainnews.nhn?date={date}"]

    links = [a["href"] for a in navi.find_all("a")]
    links = sorted(set(links))
    return links


def get_news_list(page_links: list[str]) -> list[dict]:
    """페이지 링크에서 기사 메타데이터(제목, 링크, 언론사, 발행일) 수집"""
    articles = []
    for url in page_links:
        resp = requests.get(ROOT_URL + url, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        news_list_div = soup.find("div", {"class": "mainNewsList"})
        if not news_list_div:
            continue

        press_list = [s.text.strip() for s in soup.find_all("span", {"class": "press"})]
        date_list = [s.text.strip() for s in soup.find_all("span", {"class": "wdate"})]
        links = [a for a in news_list_div.find_all("a") if a.text.strip()]

        seen = []
        news_urls = []
        for a in links:
            href = a["href"]
            if href not in seen:
                seen.append(href)
                news_urls.append((a.text.strip(), href))

        for i, (title, href) in enumerate(news_urls):
            press = press_list[i] if i < len(press_list) else ""
            dt_str = date_list[i] if i < len(date_list) else ""
            published_at = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y.%m.%d %H:%M:%S", "%Y.%m.%d %H:%M", "%Y-%m-%d %H:%M", "%Y.%m.%d", "%Y-%m-%d"):
                try:
                    published_at = datetime.strptime(dt_str, fmt)
                    break
                except ValueError:
                    continue

            articles.append({
                "title": title,
                "finance_url": ROOT_URL + href,
                "source": press,
                "published_at": published_at,
            })

    return articles


def get_article_content(finance_url: str) -> tuple[str, str]:
    """finance.naver.com 기사 URL → 리다이렉트 따라가서 본문 + 원본 URL 반환"""
    resp = requests.get(finance_url, headers=HEADERS)
    resp.raise_for_status()

    # 리다이렉트 URL 추출
    match = re.search(r"href='([^']*news\.naver\.com[^']*)'", resp.text)
    if not match:
        return "", finance_url

    original_url = match.group(1)
    resp2 = requests.get(original_url, headers=HEADERS)
    resp2.raise_for_status()
    soup = BeautifulSoup(resp2.text, "lxml")

    article = soup.find("article", {"class": "_article_content"})
    if not article:
        article = soup.select_one("#newsct_article") or soup.select_one("#articeBody")
    if not article:
        return "", original_url

    for tag in article.select("script, style, table"):
        tag.decompose()

    content = re.sub(r"\n{3,}", "\n\n", article.get_text(separator="\n", strip=True))
    return content.strip(), original_url


def crawl(max_pages: int = 3, delay: float = 0.5, date: str = None) -> list[dict]:
    """네이버 금융 메인뉴스 크롤링"""
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")
    print(f"[crawler] 크롤링 날짜: {date}")

    page_links = get_page_links(date)
    page_links = page_links[:max_pages]
    print(f"[crawler] 페이지 수: {len(page_links)}")

    articles = get_news_list(page_links)
    print(f"[crawler] 기사 목록: {len(articles)}건")

    results = []
    for article in articles:
        try:
            content, original_url = get_article_content(article["finance_url"])
            if not content:
                continue
            article["content"] = content
            article["original_url"] = original_url
            del article["finance_url"]
            results.append(article)
            time.sleep(delay)
        except Exception as e:
            print(f"[crawler] 오류 ({article['title'][:30]}): {e}")
            continue

    return results
