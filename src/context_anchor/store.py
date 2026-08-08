from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime | None = None) -> str:
    return (value or utc_now_dt()).astimezone(timezone.utc).isoformat()


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
                    error TEXT,
                    lease_token TEXT,
                    lease_expires_at TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
            if "lease_token" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN lease_token TEXT")
            if "lease_expires_at" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN lease_expires_at TEXT")
            if "attempts" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")

            # Tasks claimed by versions that predate leases cannot prove ownership.
            conn.execute(
                """
                UPDATE tasks
                SET status = 'queued', agent_id = NULL, updated_at = ?
                WHERE status = 'running' AND lease_expires_at IS NULL
                """,
                (utc_text(),),
            )

    def create_task(self, command: str) -> dict[str, Any]:
        task_id = str(uuid4())
        now = utc_text()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(id, command, status, created_at, updated_at)
                VALUES (?, ?, 'queued', ?, ?)
                """,
                (task_id, command, now, now),
            )
        task = self.get_task(task_id)
        assert task is not None
        return task

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def list_recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        if limit < 1 or limit > 100:
            raise ValueError("limit deve estar entre 1 e 100.")
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def _recover_expired_in_transaction(
        self,
        conn: sqlite3.Connection,
        *,
        now_text: str,
        max_attempts: int,
    ) -> None:
        conn.execute(
            """
            UPDATE tasks
            SET status = 'failed',
                agent_id = NULL,
                lease_token = NULL,
                lease_expires_at = NULL,
                error = 'Tarefa interrompida repetidamente; limite de tentativas atingido.',
                updated_at = ?
            WHERE status = 'running'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= ?
              AND attempts >= ?
            """,
            (now_text, now_text, max_attempts),
        )
        conn.execute(
            """
            UPDATE tasks
            SET status = 'queued',
                agent_id = NULL,
                lease_token = NULL,
                lease_expires_at = NULL,
                error = NULL,
                updated_at = ?
            WHERE status = 'running'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at <= ?
              AND attempts < ?
            """,
            (now_text, now_text, max_attempts),
        )

    def recover_expired(
        self,
        *,
        now: datetime | None = None,
        max_attempts: int = 3,
    ) -> int:
        now_text = utc_text(now)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            before = conn.total_changes
            self._recover_expired_in_transaction(
                conn,
                now_text=now_text,
                max_attempts=max_attempts,
            )
            changed = conn.total_changes - before
        return changed

    def claim_next(
        self,
        agent_id: str,
        *,
        lease_seconds: int = 120,
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds deve ser positivo.")
        now_dt = now or utc_now_dt()
        now_text = utc_text(now_dt)
        lease_expires = utc_text(now_dt + timedelta(seconds=lease_seconds))

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._recover_expired_in_transaction(
                conn,
                now_text=now_text,
                max_attempts=max_attempts,
            )
            row = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = 'queued' AND attempts < ?
                ORDER BY created_at
                LIMIT 1
                """,
                (max_attempts,),
            ).fetchone()
            if row is None:
                conn.commit()
                return None

            lease_token = str(uuid4())
            updated = conn.execute(
                """
                UPDATE tasks
                SET status = 'running',
                    agent_id = ?,
                    lease_token = ?,
                    lease_expires_at = ?,
                    attempts = attempts + 1,
                    updated_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (agent_id, lease_token, lease_expires, now_text, row["id"]),
            )
            if updated.rowcount != 1:
                conn.rollback()
                return None
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
        lease_token: str,
        ok: bool,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any] | None:
        now = utc_text()
        status = "succeeded" if ok else "failed"
        result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE tasks
                SET status = ?,
                    result_json = ?,
                    error = ?,
                    lease_token = NULL,
                    lease_expires_at = NULL,
                    updated_at = ?
                WHERE id = ? AND status = 'running' AND lease_token = ?
                """,
                (status, result_json, error, now, task_id, lease_token),
            )
            if updated.rowcount != 1:
                return None
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
            "lease_token": row["lease_token"],
            "lease_expires_at": row["lease_expires_at"],
            "attempts": row["attempts"],
        }
