import os
import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USERNAME"),
        password=os.getenv("DB_PASSWORD"),
    )
    register_vector(conn)
    return conn


def news_exists(conn, original_url: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM news WHERE original_url = %s", (original_url,))
        return cur.fetchone() is not None



def fetch_unsummarized_news(conn) -> list[dict]:
    """news_summaries가 없는 news 전체 조회 (published_at 오름차순)"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT n.id, n.title, n.content, n.published_at, n.original_url
            FROM news n
            LEFT JOIN news_summaries ns ON ns.news_id = n.id
            WHERE ns.news_id IS NULL
            ORDER BY n.published_at ASC
            """
        )
        rows = cur.fetchall()
    return [{"id": r[0], "title": r[1], "content": r[2], "published_at": r[3], "original_url": r[4]} for r in rows]


def fetch_unembedded_news(conn) -> list[dict]:
    """news_summaries는 있지만 news_embeddings가 없는 기사 조회 (published_at 오름차순)"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT n.id, ns.summary_line
            FROM news n
            JOIN news_summaries ns ON ns.news_id = n.id
            LEFT JOIN news_embeddings ne ON ne.news_id = n.id
            WHERE ne.news_id IS NULL
            ORDER BY n.published_at ASC
            """
        )
        rows = cur.fetchall()
    return [{"id": r[0], "summary_line": r[1]} for r in rows]



def insert_news(conn, title: str, content: str, source: str, original_url: str, published_at) -> int | None:

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO news (title, content, source, original_url, published_at, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (original_url) DO NOTHING
            RETURNING id
            """,
            (title, content, source, original_url, published_at),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0] if row else None


def insert_news_embedding(conn, news_id: int, embedding: list[float]):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO news_embeddings (news_id, embedding, created_at, updated_at)
            VALUES (%s, %s, NOW(), NOW())
            ON CONFLICT (news_id) DO NOTHING
            """,
            (news_id, np.array(embedding).flatten()),
        )
        conn.commit()


def insert_news_summary(conn, news_id: int, summary_line: str, category: str, region: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO news_summaries (news_id, summary_line, category, region, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (news_id) DO NOTHING
            """,
            (news_id, summary_line, category, region),
        )
        conn.commit()


def insert_news_companies(conn, news_id: int, tickers: list[str]):
    """GPT가 추출한 ticker를 companies 테이블과 매핑해 news_companies에 저장"""
    if not tickers:
        return

    with conn.cursor() as cur:
        for ticker in tickers:
            cur.execute(
                "SELECT id FROM companies WHERE ticker = %s LIMIT 1",
                (ticker,),
            )
            row = cur.fetchone()
            if not row:
                continue

            company_id = row[0]
            cur.execute(
                """
                INSERT INTO news_companies (news_id, company_id, role)
                VALUES (%s, %s, 'RELATED')
                ON CONFLICT DO NOTHING
                """,
                (news_id, company_id),
            )
        conn.commit()


