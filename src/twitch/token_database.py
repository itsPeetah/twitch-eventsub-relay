"""SQLite persistence for Twitch OAuth token responses."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS twitch_oauth (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_in INTEGER NOT NULL,
    expires_at REAL NOT NULL,
    scope TEXT
)
"""


class OAuthTokenDatabase:
    """Single-row SQLite store for Twitch ``/oauth2/token`` JSON payloads."""

    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)

    @property
    def path(self) -> Path:
        return self._path

    @staticmethod
    def _normalize_scope(tokens: dict[str, Any]) -> str | None:
        raw = tokens.get("scope")
        if raw is None:
            return None
        if isinstance(raw, list):
            return " ".join(raw)
        return str(raw)

    def load(self) -> dict[str, Any] | None:
        if not self._path.is_file():
            return None
        try:
            conn = sqlite3.connect(self._path)
            try:
                row = conn.execute(
                    "SELECT access_token, refresh_token, expires_in, expires_at, scope "
                    "FROM twitch_oauth WHERE id = 1"
                ).fetchone()
                if row is None:
                    return None
                access_token, refresh_token, expires_in, expires_at, scope = row
                out: dict[str, Any] = {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": expires_in,
                    "expires_at": expires_at,
                }
                if scope is not None:
                    out["scope"] = scope
                return out
            finally:
                conn.close()
        except sqlite3.Error:
            return None

    def save(self, twitch_token_payload: dict[str, Any]) -> dict[str, Any]:
        """Persist Twitch token JSON; adds ``expires_at``. Returns the stored blob."""
        row = dict(twitch_token_payload)
        row["expires_at"] = time.time() + row["expires_in"]
        scope_store = self._normalize_scope(row)

        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path)
        try:
            conn.execute(_CREATE_TABLE_SQL)
            conn.execute(
                """
                INSERT INTO twitch_oauth (
                    id, access_token, refresh_token, expires_in, expires_at, scope
                ) VALUES (1, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    access_token = excluded.access_token,
                    refresh_token = excluded.refresh_token,
                    expires_in = excluded.expires_in,
                    expires_at = excluded.expires_at,
                    scope = excluded.scope
                """,
                (
                    row["access_token"],
                    row["refresh_token"],
                    int(row["expires_in"]),
                    row["expires_at"],
                    scope_store,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return row

    def clear(self) -> None:
        try:
            if self._path.is_file():
                conn = sqlite3.connect(self._path)
                try:
                    conn.execute("DELETE FROM twitch_oauth WHERE id = 1")
                    conn.commit()
                finally:
                    conn.close()
        except (OSError, sqlite3.Error):
            pass
