from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    agent_id TEXT,
                    result_json TEXT,
                    error TEXT
                )
                """
            )

    def create_task(self, command: str) -> dict[str, Any]:
        task_id = str(uuid4())
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(id, command, status, created_at, updated_at)
                VALUES (?, ?, 'queued', ?, ?)
                """,
                (task_id, command, now, now),
            )
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def claim_next(self, agent_id: str) -> dict[str, Any] | None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM tasks WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                conn.commit()
                return None

            now = utc_now()
            conn.execute(
                """
                UPDATE tasks
                SET status = 'running', agent_id = ?, updated_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (agent_id, now, row["id"]),
            )
            conn.commit()
            return self.get_task(row["id"])
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def complete_task(
        self,
        task_id: str,
        *,
        ok: bool,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        now = utc_now()
        status = "succeeded" if ok else "failed"
        result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, result_json = ?, error = ?, updated_at = ?
                WHERE id = ? AND status = 'running'
                """,
                (status, result_json, error, now, task_id),
            )
        return self.get_task(task_id)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = json.loads(row["result_json"]) if row["result_json"] else None
        return {
            "id": row["id"],
            "command": row["command"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "agent_id": row["agent_id"],
            "result": result,
            "error": row["error"],
        }
