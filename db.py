from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional

import aiosqlite

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS requests (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id          TEXT,
    timestamp_utc       TEXT NOT NULL,
    model               TEXT,
    path                TEXT,
    stream              INTEGER,
    ttfb_s              REAL,
    total_s             REAL,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    cache_write_tokens  INTEGER,
    cache_read_tokens   INTEGER,
    cost_usd            REAL,
    stop_reason         TEXT,
    request_body        TEXT,
    response_body       TEXT,
    error_body          TEXT,
    status_code         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ts ON requests(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_model ON requests(model);
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


async def init_db(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    await conn.executescript("PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;")
    await conn.executescript(_CREATE_TABLE)
    await conn.commit()
    return conn


async def insert_record(conn: aiosqlite.Connection, rec: RequestRecord, max_body_bytes: int) -> None:
    def _trunc(s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        if len(s.encode()) > max_body_bytes:
            return s.encode()[:max_body_bytes].decode(errors="replace") + "…[truncated]"
        return s

    try:
        await conn.execute(
            """
            INSERT INTO requests (
                request_id, timestamp_utc, model, path, stream,
                ttfb_s, total_s,
                input_tokens, output_tokens, cache_write_tokens, cache_read_tokens,
                cost_usd, stop_reason,
                request_body, response_body, error_body, status_code
            ) VALUES (
                :request_id, :timestamp_utc, :model, :path, :stream,
                :ttfb_s, :total_s,
                :input_tokens, :output_tokens, :cache_write_tokens, :cache_read_tokens,
                :cost_usd, :stop_reason,
                :request_body, :response_body, :error_body, :status_code
            )
            """,
            {
                **asdict(rec),
                "stream": int(rec.stream),
                "request_body": _trunc(rec.request_body),
                "response_body": _trunc(rec.response_body),
            },
        )
        await conn.commit()
    except Exception:
        logger.exception("Failed to insert request record")


async def row_count(conn: aiosqlite.Connection) -> int:
    async with conn.execute("SELECT COUNT(*) FROM requests") as cur:
        row = await cur.fetchone()
        return row[0] if row else 0
