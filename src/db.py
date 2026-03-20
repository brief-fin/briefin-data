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


def is_similar_to_recent(conn, embedding: list[float], hours: int = 3, threshold: float = 0.7) -> tuple[bool, str | None]:
    """최근 N시간 이내 뉴스와 코사인 유사도 검사. threshold 이상이면 (True, 유사 뉴스 제목) 반환"""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT n.title, 1 - (ne.embedding <=> %s) AS similarity
            FROM news_embeddings ne
            JOIN news n ON ne.news_id = n.id
            WHERE n.created_at > NOW() - INTERVAL '1 hour' * %s
              AND 1 - (ne.embedding <=> %s) >= %s
            ORDER BY similarity DESC
            LIMIT 1
            """,
            (np.array(embedding).flatten(), hours, np.array(embedding).flatten(), threshold),
        )
        row = cur.fetchone()
        if row:
            return True, f"{row[0][:40]} (유사도: {row[1]:.2f})"
        return False, None


def insert_news(conn, title: str, content: str, source: str, original_url: str, published_at) -> int | None:
    if hasattr(published_at, "date"):
        published_at = published_at.date()

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
