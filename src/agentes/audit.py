"""Append-only log of every tool call the agent makes."""

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

AuditStatus = Literal["executed", "rejected", "error"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('executed', 'rejected', 'error')),
    result TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class AuditEntry:
    id: int
    timestamp: datetime
    thread_id: str
    tool: str
    args: dict[str, Any]
    status: AuditStatus
    result: str


class AuditLog:
    """Records tool calls; offers no way to edit or delete them."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        with self._conn:
            self._conn.execute(_SCHEMA)

    def record(
        self,
        thread_id: str,
        tool: str,
        args: Mapping[str, Any],
        status: AuditStatus,
        result: str,
    ) -> AuditEntry:
        now = datetime.now(UTC)
        payload = json.dumps(dict(args), ensure_ascii=False, default=str)
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO audit_log (timestamp, thread_id, tool, args, status, result) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (now.isoformat(), thread_id, tool, payload, status, result),
            )
        return AuditEntry(
            id=int(cursor.lastrowid or 0),
            timestamp=now,
            thread_id=thread_id,
            tool=tool,
            args=json.loads(payload),
            status=status,
            result=result,
        )

    def entries(self, thread_id: str | None = None, limit: int = 100) -> list[AuditEntry]:
        """Most recent entries first, optionally for one conversation."""
        query = "SELECT id, timestamp, thread_id, tool, args, status, result FROM audit_log"
        params: list[Any] = []
        if thread_id is not None:
            query += " WHERE thread_id = ?"
            params.append(thread_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        return [
            AuditEntry(
                id=row[0],
                timestamp=datetime.fromisoformat(row[1]),
                thread_id=row[2],
                tool=row[3],
                args=json.loads(row[4]),
                status=cast(AuditStatus, row[5]),
                result=row[6],
            )
            for row in self._conn.execute(query, params)
        ]
