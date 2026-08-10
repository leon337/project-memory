from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from context_anchor.lease import LeaseGuardedExecutor
from context_anchor.policy import Plan
from context_anchor.store import TaskStore


def _create_legacy_db(
    db_path: Path,
    *,
    status: str,
    attempts: int,
    lease_token: str | None = None,
    lease_expires_at: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE tasks (
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
        conn.execute(
            """
            INSERT INTO tasks(
                id, command, status, created_at, updated_at, agent_id,
                lease_token, lease_expires_at, attempts
            )
            VALUES ('legacy-1', 'digitar texto', ?, ?, ?, 'old-agent', ?, ?, ?)
            """,
            (status, now, now, lease_token, lease_expires_at, attempts),
        )


def test_legacy_running_task_without_journal_is_failed_closed_on_migration(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy-running.db"
    _create_legacy_db(
        db_path,
        status="running",
        attempts=1,
        lease_token="l" * 24,
        lease_expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    )

    store = TaskStore(db_path)
    task = store.get_task("legacy-1")

    assert task is not None
    assert task["status"] == "failed"
    assert "sem journal durável" in str(task["error"])
    assert store.claim_next("new-agent") is None


def test_legacy_requeued_task_with_prior_attempt_is_failed_closed_on_migration(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy-requeued.db"
    _create_legacy_db(db_path, status="queued", attempts=1)

    store = TaskStore(db_path)
    task = store.get_task("legacy-1")

    assert task is not None
    assert task["status"] == "failed"
    assert store.claim_next("new-agent") is None


def test_legacy_never_started_queued_task_can_be_claimed_under_journal_v1(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy-safe.db"
    _create_legacy_db(db_path, status="queued", attempts=0)

    store = TaskStore(db_path)
    claimed = store.claim_next("new-agent")

    assert claimed is not None
    assert claimed["id"] == "legacy-1"
    assert claimed["status"] == "running"
    with sqlite3.connect(db_path) as conn:
        journal_version = conn.execute(
            "SELECT journal_version FROM tasks WHERE id = 'legacy-1'"
        ).fetchone()[0]
    assert journal_version == 1


class _Heartbeat:
    task_id = "fault-task"
    lease_token = "t" * 24

    def assert_owned(self) -> None:
        return None


class _Physical:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _: Plan) -> dict[str, Any]:
        self.calls += 1
        return {"action": "type_text", "verified": True, "characters": 4}


class _CrashBeforeExecutedJournal:
    def __init__(self) -> None:
        self.state = "prepared"
        self.key: str | None = None

    def prepare(self, *, action_key: str, action_name: str, repeat_safe: bool) -> dict[str, Any]:
        self.key = action_key
        return {
            "action_key": action_key,
            "action_name": action_name,
            "repeat_safe": repeat_safe,
            "state": self.state,
            "receipt": None,
        }

    def transition(
        self,
        *,
        action_key: str,
        state: str,
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if state == "in_flight":
            self.state = state
            return {"action_key": action_key, "state": state, "receipt": None}
        raise RuntimeError("fault injection: crash after physical effect before executed receipt")


def test_fault_after_physical_return_before_executed_receipt_leaves_ambiguous_state() -> None:
    physical = _Physical()
    journal = _CrashBeforeExecutedJournal()
    guarded = LeaseGuardedExecutor(physical, _Heartbeat(), journal=journal)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="fault injection"):
        guarded.execute(Plan("type_text", "texto"))

    assert physical.calls == 1
    assert journal.state == "in_flight"

    class _RecoveredJournal(_CrashBeforeExecutedJournal):
        def prepare(self, *, action_key: str, action_name: str, repeat_safe: bool) -> dict[str, Any]:
            return {
                "action_key": action_key,
                "action_name": action_name,
                "repeat_safe": repeat_safe,
                "state": "in_flight",
                "receipt": None,
            }

    recovered_physical = _Physical()
    recovered = LeaseGuardedExecutor(
        recovered_physical,
        _Heartbeat(),
        journal=_RecoveredJournal(),
    )  # type: ignore[arg-type]

    with pytest.raises(Exception, match="replay físico cego"):
        recovered.execute(Plan("type_text", "texto"))

    assert recovered_physical.calls == 0
