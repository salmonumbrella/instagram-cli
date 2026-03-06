import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from ig_cli.config import DIR_MODE, FILE_MODE


class SafetyStateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.chmod(DIR_MODE)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        if self.db_path.exists():
            os.chmod(self.db_path, FILE_MODE)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS breaker_state (
                    account TEXT NOT NULL,
                    scope_group TEXT NOT NULL,
                    state TEXT NOT NULL,
                    consecutive_failures INTEGER NOT NULL,
                    failures_window INTEGER NOT NULL,
                    window_started_at REAL NOT NULL,
                    opened_until REAL NOT NULL,
                    half_open_probes INTEGER NOT NULL,
                    consecutive_successes INTEGER NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (account, scope_group)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_bucket (
                    account TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    tokens REAL NOT NULL,
                    last_refill_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (account, bucket)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS global_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def get_breaker(self, account: str, scope_group: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT state, consecutive_failures, failures_window, window_started_at,
                       opened_until, half_open_probes, consecutive_successes, updated_at
                FROM breaker_state
                WHERE account = ? AND scope_group = ?
                """,
                (account, scope_group),
            ).fetchone()
        if row is None:
            return {
                "state": "closed",
                "consecutive_failures": 0,
                "failures_window": 0,
                "window_started_at": 0.0,
                "opened_until": 0.0,
                "half_open_probes": 0,
                "consecutive_successes": 0,
                "updated_at": 0.0,
            }
        return dict(row)

    def upsert_breaker(self, account: str, scope_group: str, record: dict[str, Any]) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO breaker_state (
                    account, scope_group, state, consecutive_failures, failures_window,
                    window_started_at, opened_until, half_open_probes, consecutive_successes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account, scope_group) DO UPDATE SET
                    state = excluded.state,
                    consecutive_failures = excluded.consecutive_failures,
                    failures_window = excluded.failures_window,
                    window_started_at = excluded.window_started_at,
                    opened_until = excluded.opened_until,
                    half_open_probes = excluded.half_open_probes,
                    consecutive_successes = excluded.consecutive_successes,
                    updated_at = excluded.updated_at
                """,
                (
                    account,
                    scope_group,
                    record["state"],
                    int(record["consecutive_failures"]),
                    int(record["failures_window"]),
                    float(record["window_started_at"]),
                    float(record["opened_until"]),
                    int(record["half_open_probes"]),
                    int(record["consecutive_successes"]),
                    now,
                ),
            )

    def list_breakers(self, account: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT scope_group, state, consecutive_failures, failures_window,
                       window_started_at, opened_until, half_open_probes, consecutive_successes, updated_at
                FROM breaker_state
                WHERE account = ?
                ORDER BY scope_group
                """,
                (account,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_breakers(self, account: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM breaker_state WHERE account = ?", (account,))

    def get_bucket(self, account: str, bucket: str, capacity: float, now: float) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT tokens, last_refill_at, updated_at
                FROM rate_bucket
                WHERE account = ? AND bucket = ?
                """,
                (account, bucket),
            ).fetchone()
        if row is None:
            return {
                "tokens": capacity,
                "last_refill_at": now,
                "updated_at": now,
            }
        return dict(row)

    def upsert_bucket(
        self, account: str, bucket: str, tokens: float, last_refill_at: float
    ) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO rate_bucket (account, bucket, tokens, last_refill_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account, bucket) DO UPDATE SET
                    tokens = excluded.tokens,
                    last_refill_at = excluded.last_refill_at,
                    updated_at = excluded.updated_at
                """,
                (account, bucket, float(tokens), float(last_refill_at), now),
            )

    def list_buckets(self, account: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT bucket, tokens, last_refill_at, updated_at
                FROM rate_bucket
                WHERE account = ?
                ORDER BY bucket
                """,
                (account,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_buckets(self, account: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM rate_bucket WHERE account = ?", (account,))

    def get_global_float(self, key: str, default: float = 0.0) -> float:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM global_state WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return default
        try:
            return float(json.loads(row["value"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

    def set_global_float(self, key: str, value: float) -> None:
        now = time.time()
        payload = json.dumps(float(value))
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO global_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, payload, now),
            )

    def reset_account(self, account: str) -> None:
        self.clear_breakers(account)
        self.clear_buckets(account)
