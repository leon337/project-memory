from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx

from .redaction import redact_payload

ActionJournalState = Literal["prepared", "in_flight", "executed", "acknowledged"]

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "prepared": frozenset({"prepared", "in_flight"}),
    "in_flight": frozenset({"in_flight", "executed"}),
    "executed": frozenset({"executed"}),
    "acknowledged": frozenset({"acknowledged"}),
}


class ActionJournalError(RuntimeError):
    """Base class for durable action journal failures."""


class ActionJournalLeaseConflict(ActionJournalError):
    """The task is no longer owned by the lease attempting the journal change."""


class ActionJournalConflict(ActionJournalError):
    """A journal entry exists but does not match the requested action contract."""


class ActionReplayBlocked(ActionJournalError):
    """Recovery reached an ambiguous non-repeatable physical action."""

    def __init__(self, action_key: str, state: str) -> None:
        super().__init__(
            f"Ação {action_key!r} está em estado durável {state!r}; "
            "replay físico cego foi bloqueado."
        )
        self.action_key = action_key
        self.state = state


def utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    receipt = json.loads(row["receipt_json"]) if row["receipt_json"] else None
    return {
        "task_id": row["task_id"],
        "action_key": row["action_key"],
        "action_name": row["action_name"],
        "repeat_safe": bool(row["repeat_safe"]),
        "state": row["state"],
        "receipt": receipt,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "acknowledged_at": row["acknowledged_at"],
    }


class ActionJournalStore:
    """SQLite journal shared with the Central task database.

    The journal stores only action identity, lifecycle state and a deliberately
    small sanitized receipt. Raw command targets, typed text, credentials,
    screenshots and full URLs are not part of this schema.
    """

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
                CREATE TABLE IF NOT EXISTS action_journal (
                    task_id TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    action_name TEXT NOT NULL,
                    repeat_safe INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL,
                    receipt_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    acknowledged_at TEXT,
                    PRIMARY KEY(task_id, action_key)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_action_journal_state_updated
                ON action_journal(state, updated_at)
                """
            )

    @staticmethod
    def _assert_live_lease(
        conn: sqlite3.Connection,
        *,
        task_id: str,
        lease_token: str,
        now_text: str,
    ) -> None:
        row = conn.execute(
            """
            SELECT id
            FROM tasks
            WHERE id = ?
              AND status = 'running'
              AND lease_token = ?
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at > ?
            """,
            (task_id, lease_token, now_text),
        ).fetchone()
        if row is None:
            raise ActionJournalLeaseConflict(
                "Lease da tarefa expirou ou não pertence mais a esta execução."
            )

    def get(self, task_id: str, action_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM action_journal WHERE task_id = ? AND action_key = ?",
                (task_id, action_key),
            ).fetchone()
        return _row_to_dict(row) if row is not None else None

    def prepare(
        self,
        *,
        task_id: str,
        lease_token: str,
        action_key: str,
        action_name: str,
        repeat_safe: bool,
    ) -> dict[str, Any]:
        if not action_key or len(action_key) > 160:
            raise ValueError("action_key inválido.")
        if not action_name or len(action_name) > 80:
            raise ValueError("action_name inválido.")
        now = utc_now_text()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._assert_live_lease(
                conn,
                task_id=task_id,
                lease_token=lease_token,
                now_text=now,
            )
            row = conn.execute(
                "SELECT * FROM action_journal WHERE task_id = ? AND action_key = ?",
                (task_id, action_key),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO action_journal(
                        task_id, action_key, action_name, repeat_safe, state,
                        receipt_json, created_at, updated_at, acknowledged_at
                    )
                    VALUES (?, ?, ?, ?, 'prepared', NULL, ?, ?, NULL)
                    """,
                    (task_id, action_key, action_name, int(repeat_safe), now, now),
                )
                row = conn.execute(
                    "SELECT * FROM action_journal WHERE task_id = ? AND action_key = ?",
                    (task_id, action_key),
                ).fetchone()
            else:
                if row["action_name"] != action_name or bool(row["repeat_safe"]) != repeat_safe:
                    raise ActionJournalConflict(
                        "A identidade durável da ação não corresponde ao contrato já persistido."
                    )
            conn.commit()
            assert row is not None
            return _row_to_dict(row)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def transition(
        self,
        *,
        task_id: str,
        lease_token: str,
        action_key: str,
        state: ActionJournalState,
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now_text()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._assert_live_lease(
                conn,
                task_id=task_id,
                lease_token=lease_token,
                now_text=now,
            )
            row = conn.execute(
                "SELECT * FROM action_journal WHERE task_id = ? AND action_key = ?",
                (task_id, action_key),
            ).fetchone()
            if row is None:
                raise ActionJournalConflict("Ação não foi preparada antes da transição.")
            current = str(row["state"])
            if state not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise ActionJournalConflict(
                    f"Transição inválida do journal: {current!r} -> {state!r}."
                )
            if receipt is not None and state != "executed":
                raise ActionJournalConflict("Receipt só pode ser persistido em executed.")
            serialized_receipt = row["receipt_json"]
            if receipt is not None:
                serialized_receipt = json.dumps(
                    redact_payload(receipt),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            conn.execute(
                """
                UPDATE action_journal
                SET state = ?, receipt_json = ?, updated_at = ?
                WHERE task_id = ? AND action_key = ?
                """,
                (state, serialized_receipt, now, task_id, action_key),
            )
            updated = conn.execute(
                "SELECT * FROM action_journal WHERE task_id = ? AND action_key = ?",
                (task_id, action_key),
            ).fetchone()
            conn.commit()
            assert updated is not None
            return _row_to_dict(updated)
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def acknowledge_task(self, task_id: str) -> int:
        """Mark journal rows terminal after the Central accepted task result."""

        now = utc_now_text()
        with self._connect() as conn:
            terminal = conn.execute(
                "SELECT status FROM tasks WHERE id = ? AND status IN ('succeeded', 'failed')",
                (task_id,),
            ).fetchone()
            if terminal is None:
                return 0
            before = conn.total_changes
            conn.execute(
                """
                UPDATE action_journal
                SET state = 'acknowledged',
                    acknowledged_at = COALESCE(acknowledged_at, ?),
                    updated_at = ?
                WHERE task_id = ? AND state != 'acknowledged'
                """,
                (now, now, task_id),
            )
            return conn.total_changes - before

    def reconcile_terminal_tasks(self) -> int:
        """Repair the narrow crash window between task ACK and journal marking."""

        now = utc_now_text()
        with self._connect() as conn:
            before = conn.total_changes
            conn.execute(
                """
                UPDATE action_journal
                SET state = 'acknowledged',
                    acknowledged_at = COALESCE(acknowledged_at, ?),
                    updated_at = ?
                WHERE state != 'acknowledged'
                  AND EXISTS (
                      SELECT 1 FROM tasks
                      WHERE tasks.id = action_journal.task_id
                        AND tasks.status IN ('succeeded', 'failed')
                  )
                """,
                (now, now),
            )
            return conn.total_changes - before

    def prune_acknowledged(self, *, older_than: datetime) -> int:
        cutoff = older_than.astimezone(timezone.utc).isoformat()
        with self._connect() as conn:
            before = conn.total_changes
            conn.execute(
                """
                DELETE FROM action_journal
                WHERE state = 'acknowledged'
                  AND acknowledged_at IS NOT NULL
                  AND acknowledged_at <= ?
                """,
                (cutoff,),
            )
            return conn.total_changes - before


class ActionJournalClient:
    """Agent-side client for the Central journal API."""

    def __init__(
        self,
        *,
        task_id: str,
        lease_token: str,
        client_factory: Callable[[], httpx.Client],
    ) -> None:
        self.task_id = task_id
        self.lease_token = lease_token
        self._client_factory = client_factory

    def _post(self, suffix: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._client_factory() as client:
            response = client.post(
                f"/api/agent/tasks/{self.task_id}/actions/{suffix}",
                json={"lease_token": self.lease_token, **payload},
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ActionJournalError("Central retornou resposta inválida do journal.")
        return data

    def prepare(
        self,
        *,
        action_key: str,
        action_name: str,
        repeat_safe: bool,
    ) -> dict[str, Any]:
        return self._post(
            "prepare",
            {
                "action_key": action_key,
                "action_name": action_name,
                "repeat_safe": repeat_safe,
            },
        )

    def transition(
        self,
        *,
        action_key: str,
        state: ActionJournalState,
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"action_key": action_key, "state": state}
        if receipt is not None:
            payload["receipt"] = receipt
        return self._post("transition", payload)


__all__ = [
    "ActionJournalClient",
    "ActionJournalConflict",
    "ActionJournalError",
    "ActionJournalLeaseConflict",
    "ActionJournalState",
    "ActionJournalStore",
    "ActionReplayBlocked",
]
