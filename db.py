from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS requests (
    id                  SERIAL PRIMARY KEY,
    request_id          TEXT,
    timestamp_utc       TIMESTAMPTZ NOT NULL,
    model               TEXT,
    path                TEXT,
    stream              BOOLEAN,
    ttfb_s              DOUBLE PRECISION,
    total_s             DOUBLE PRECISION,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    cache_write_tokens  INTEGER,
    cache_read_tokens   INTEGER,
    cost_usd            DOUBLE PRECISION,
    stop_reason         TEXT,
    request_body        TEXT,
    response_body       TEXT,
    error_body          TEXT,
    status_code         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ts ON requests(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_model ON requests(model);
ALTER TABLE requests ADD COLUMN IF NOT EXISTS original_request_body TEXT;
"""


@dataclass
class RequestRecord:
    request_id: Optional[str]
    timestamp_utc: str
    model: Optional[str]
    path: str
    stream: bool
    ttfb_s: Optional[float]
    total_s: Optional[float]
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost_usd: float
    stop_reason: Optional[str]
    request_body: Optional[str]
    response_body: Optional[str]
    error_body: Optional[str]
    status_code: Optional[int]
    original_request_body: Optional[str] = None


def get_pool(database_url: str) -> ThreadedConnectionPool:
    return ThreadedConnectionPool(1, 10, dsn=database_url)


def close_pool(pool: ThreadedConnectionPool) -> None:
    pool.closeall()


@contextmanager
def _conn(pool: ThreadedConnectionPool):
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def init_db(pool: ThreadedConnectionPool) -> None:
    with _conn(pool) as conn:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)


def insert_record(pool: ThreadedConnectionPool, rec: RequestRecord, max_body_bytes: int) -> None:
    def _trunc(s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        if len(s.encode()) > max_body_bytes:
            return s.encode()[:max_body_bytes].decode(errors="replace") + "…[truncated]"
        return s

    data = asdict(rec)
    data["request_body"] = _trunc(rec.request_body)
    data["response_body"] = _trunc(rec.response_body)
    data["original_request_body"] = _trunc(rec.original_request_body)

    sql = """
        INSERT INTO requests (
            request_id, timestamp_utc, model, path, stream,
            ttfb_s, total_s,
            input_tokens, output_tokens, cache_write_tokens, cache_read_tokens,
            cost_usd, stop_reason,
            request_body, response_body, error_body, status_code, original_request_body
        ) VALUES (
            %(request_id)s, %(timestamp_utc)s, %(model)s, %(path)s, %(stream)s,
            %(ttfb_s)s, %(total_s)s,
            %(input_tokens)s, %(output_tokens)s, %(cache_write_tokens)s, %(cache_read_tokens)s,
            %(cost_usd)s, %(stop_reason)s,
            %(request_body)s, %(response_body)s, %(error_body)s, %(status_code)s, %(original_request_body)s
        )
    """
    try:
        with _conn(pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, data)
    except Exception:
        logger.exception("Failed to insert request record")


def list_requests(
    pool: ThreadedConnectionPool,
    limit: int = 50,
    offset: int = 0,
    model: Optional[str] = None,
    status: Optional[int] = None,
) -> list[dict]:
    where = []
    params: list = []
    if model:
        where.append("model = %s")
        params.append(model)
    if status:
        where.append("status_code = %s")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT id, request_id, timestamp_utc, model, path, stream, ttfb_s, total_s,
               input_tokens, output_tokens, cache_write_tokens, cache_read_tokens,
               cost_usd, stop_reason, status_code
        FROM requests
        {where_sql}
        ORDER BY id DESC
        LIMIT %s OFFSET %s
    """
    params += [limit, offset]
    with _conn(pool) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())


def count_requests(pool: ThreadedConnectionPool, model: Optional[str] = None, status: Optional[int] = None) -> int:
    where = []
    params: list = []
    if model:
        where.append("model = %s")
        params.append(model)
    if status:
        where.append("status_code = %s")
        params.append(status)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with _conn(pool) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM requests {where_sql}", params)
            row = cur.fetchone()
            return row[0] if row else 0


def get_request(pool: ThreadedConnectionPool, req_id: int) -> Optional[dict]:
    with _conn(pool) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM requests WHERE id = %s", (req_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def distinct_models(pool: ThreadedConnectionPool) -> list[str]:
    with _conn(pool) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT model FROM requests WHERE model IS NOT NULL ORDER BY model")
            return [r[0] for r in cur.fetchall()]


def cost_summary(pool: ThreadedConnectionPool) -> dict:
    with _conn(pool) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT COUNT(*) AS request_count,
                       COALESCE(SUM(cost_usd), 0) AS total_cost,
                       COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS total_output_tokens
                FROM requests
            """)
            return dict(cur.fetchone())


def cost_by_model(pool: ThreadedConnectionPool) -> list[dict]:
    with _conn(pool) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT model,
                       COUNT(*) AS request_count,
                       COALESCE(SUM(cost_usd), 0) AS total_cost,
                       COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS total_output_tokens
                FROM requests
                GROUP BY model
                ORDER BY total_cost DESC
            """)
            return list(cur.fetchall())


def list_responses_for_folder_breakdown(pool: ThreadedConnectionPool) -> list[dict]:
    with _conn(pool) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT stream, response_body, cost_usd, input_tokens, output_tokens FROM requests")
            return list(cur.fetchall())


def cost_over_time(pool: ThreadedConnectionPool, days: int = 14) -> list[dict]:
    with _conn(pool) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT date_trunc('day', timestamp_utc) AS day,
                       COALESCE(SUM(cost_usd), 0) AS total_cost,
                       COUNT(*) AS request_count
                FROM requests
                WHERE timestamp_utc > now() - (%s || ' days')::interval
                GROUP BY day
                ORDER BY day
                """,
                (days,),
            )
            return list(cur.fetchall())
