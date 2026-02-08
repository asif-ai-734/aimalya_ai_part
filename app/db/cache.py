import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings


settings = get_settings()


def _ensure_db_dir(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    _ensure_db_dir(settings.DB_PATH)
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_cache_sync() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


async def init_cache() -> None:
    await asyncio.to_thread(_init_cache_sync)


def make_cache_key(kind: str, model: str, prompt_version: str, input_obj: dict) -> str:
    raw = json.dumps(input_obj, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{kind}:{model}:{prompt_version}:{digest}"


def _get_cached_response_sync(cache_key: str) -> dict | None:
    _init_cache_sync()
    with _connect() as conn:
        row = conn.execute(
            "SELECT payload FROM llm_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])


async def get_cached_response(cache_key: str) -> dict | None:
    return await asyncio.to_thread(_get_cached_response_sync, cache_key)


def _set_cached_response_sync(
    cache_key: str,
    payload: dict,
    kind: str,
    model: str,
    prompt_version: str,
) -> None:
    _init_cache_sync()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO llm_cache
            (cache_key, kind, model, prompt_version, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                kind,
                model,
                prompt_version,
                json.dumps(payload, ensure_ascii=True),
                datetime.utcnow().isoformat(),
            ),
        )


async def set_cached_response(
    cache_key: str,
    payload: dict,
    kind: str,
    model: str,
    prompt_version: str,
) -> None:
    await asyncio.to_thread(
        _set_cached_response_sync,
        cache_key,
        payload,
        kind,
        model,
        prompt_version,
    )
