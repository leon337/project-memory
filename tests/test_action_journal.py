from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from context_anchor.action_journal import (
    ActionJournalStore,
    ActionReplayBlocked,
)
from context_anchor.lease import LeaseGuardedExecutor
from context_anchor.policy import Plan
from context_anchor.store import TaskStore


def _claimed_task(store: TaskStore, *, now: datetime | None = None) -> dict[str, Any]:
    created = store.create_task("digitar texto de teste")
    claimed = store.claim_next(
        "agent-a",
        lease_seconds=120,
        max_attempts=3,
        now=now,
    )
    assert claimed is not None
    assert claimed["id"] == created["id"]
    return claimed


def test_journal_migrates_existing_database_without_changing_task(tmp_path: Path) -> None:
    db_path = tmp_path / "context.db"
    tasks = TaskStore(db_path)
    task = tasks.create_task("janela ativa")

    journal = ActionJournalStore(db_path)

    assert tasks.get_task(task["id"])["status"] == "queued"  # type: ignore[index]
    assert journal.get(task["id"], "v1:active_window:0001") is None


def test_executed_action_survives_reclaim_and_is_correlated_by_task_and_key(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    db_path = tmp_path / "context.db"
    tasks = TaskStore(db_path)
    journal = ActionJournalStore(db_path)
    first = _claimed_task(tasks, now=now)
    action_key = "v1:type_text:manual-test-key"

    prepared = journal.prepare(
        task_id=first["id"],
        lease_token=first["lease_token"],
        action_key=action_key,
        action_name="type_text",
        repeat_safe=False,
    )
    assert prepared["state"] == "prepared"
    journal.transition(
        task_id=first["id"],
        lease_token=first["lease_token"],
        action_key=action_key,
        state="in_flight",
    )
    journal.transition(
        task_id=first["id"],
        lease_token=first["lease_token"],
        action_key=action_key,
        state="executed",
        receipt={"action": "type_text", "verified": True, "characters": 5},
    )

    reclaim_time = now + timedelta(seconds=121)
    tasks.recover_expired(now=reclaim_time, max_attempts=3)
    second = tasks.claim_next(
        "agent-b",
        lease_seconds=120,
        max_attempts=3,
        now=reclaim_time,
    )
    assert second is not None
    assert second["id"] == first["id"]
    assert second["lease_token"] != first["lease_token"]

    recovered = journal.prepare(
        task_id=second["id"],
        lease_token=second["lease_token"],
        action_key=action_key,
        action_name="type_text",
        repeat_safe=False,
    )

    assert recovered["state"] == "executed"
    assert recovered["receipt"] == {
        "action": "type_text",
        "verified": True,
        "characters": 5,
    }


def test_prepared_state_proves_backend_was_not_entered_and_can_continue_after_reclaim(
    tmp_path: Path,
) -> None:
    now = datetime.now(timezone.utc)
    db_path = tmp_path / "context.db"
    tasks = TaskStore(db_path)
    journal = ActionJournalStore(db_path)
    first = _claimed_task(tasks, now=now)
    action_key = "v1:open_app:manual-test-key"
    journal.prepare(
        task_id=first["id"],
        lease_token=first["lease_token"],
        action_key=action_key,
        action_name="open_app",
        repeat_safe=False,
    )

    reclaim_time = now + timedelta(seconds=121)
    tasks.recover_expired(now=reclaim_time, max_attempts=3)
    second = tasks.claim_next(
        "agent-b",
        lease_seconds=120,
        max_attempts=3,
        now=reclaim_time,
    )
    assert second is not None

    recovered = journal.prepare(
        task_id=second["id"],
        lease_token=second["lease_token"],
        action_key=action_key,
        action_name="open_app",
        repeat_safe=False,
    )

    assert recovered["state"] == "prepared"


def test_terminal_task_reconciliation_repairs_crash_after_central_ack(tmp_path: Path) -> None:
    db_path = tmp_path / "context.db"
    tasks = TaskStore(db_path)
    journal = ActionJournalStore(db_path)
    claimed = _claimed_task(tasks)
    action_key = "v1:open_app:manual-test-key"
    journal.prepare(
        task_id=claimed["id"],
        lease_token=claimed["lease_token"],
        action_key=action_key,
        action_name="open_app",
        repeat_safe=False,
    )
    journal.transition(
        task_id=claimed["id"],
        lease_token=claimed["lease_token"],
        action_key=action_key,
        state="in_flight",
    )
    journal.transition(
        task_id=claimed["id"],
        lease_token=claimed["lease_token"],
        action_key=action_key,
        state="executed",
        receipt={"action": "open_app", "verified": True, "pid": 123},
    )
    completed = tasks.complete_task(
        claimed["id"],
        lease_token=claimed["lease_token"],
        ok=True,
        result={"status": "succeeded"},
    )
    assert completed is not None
    assert journal.get(claimed["id"], action_key)["state"] == "executed"  # type: ignore[index]

    repaired = ActionJournalStore(db_path).reconcile_terminal_tasks()

    assert repaired == 1
    assert journal.get(claimed["id"], action_key)["state"] == "acknowledged"  # type: ignore[index]


def test_acknowledged_rows_are_only_pruned_after_retention_cutoff(tmp_path: Path) -> None:
    db_path = tmp_path / "context.db"
    tasks = TaskStore(db_path)
    journal = ActionJournalStore(db_path)
    claimed = _claimed_task(tasks)
    key = "v1:active_window:manual-test-key"
    journal.prepare(
        task_id=claimed["id"],
        lease_token=claimed["lease_token"],
        action_key=key,
        action_name="active_window",
        repeat_safe=True,
    )
    completed = tasks.complete_task(
        claimed["id"],
        lease_token=claimed["lease_token"],
        ok=False,
        result=None,
        error="encerrado",
    )
    assert completed is not None
    assert journal.acknowledge_task(claimed["id"]) == 1

    assert journal.prune_acknowledged(
        older_than=datetime.now(timezone.utc) - timedelta(days=1)
    ) == 0
    assert journal.get(claimed["id"], key) is not None

    assert journal.prune_acknowledged(
        older_than=datetime.now(timezone.utc) + timedelta(seconds=1)
    ) == 1
    assert journal.get(claimed["id"], key) is None


class _Heartbeat:
    task_id = "task-1"
    lease_token = "t" * 24

    def assert_owned(self) -> None:
        return None


class _PhysicalExecutor:
    def __init__(self, receipt: dict[str, Any] | None = None) -> None:
        self.calls = 0
        self.receipt = receipt or {"action": "type_text", "verified": True, "characters": 5}

    def execute(self, _: Plan) -> dict[str, Any]:
        self.calls += 1
        return dict(self.receipt)


class _FakeJournal:
    def __init__(self, state: str, receipt: dict[str, Any] | None = None) -> None:
        self.state = state
        self.receipt = receipt
        self.prepared_keys: list[str] = []
        self.transitions: list[str] = []

    def prepare(self, *, action_key: str, action_name: str, repeat_safe: bool) -> dict[str, Any]:
        self.prepared_keys.append(action_key)
        return {
            "task_id": "task-1",
            "action_key": action_key,
            "action_name": action_name,
            "repeat_safe": repeat_safe,
            "state": self.state,
            "receipt": self.receipt,
        }

    def transition(
        self,
        *,
        action_key: str,
        state: str,
        receipt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.transitions.append(state)
        self.state = state
        if receipt is not None:
            self.receipt = receipt
        return {"action_key": action_key, "state": state, "receipt": self.receipt}


def test_executor_persists_in_flight_before_entering_non_idempotent_backend() -> None:
    physical = _PhysicalExecutor()
    journal = _FakeJournal("prepared")
    guarded = LeaseGuardedExecutor(physical, _Heartbeat(), journal=journal)  # type: ignore[arg-type]

    result = guarded.execute(Plan("type_text", "segredo que não pode ir ao journal"))

    assert physical.calls == 1
    assert len(journal.prepared_keys) == 1
    key = journal.prepared_keys[0]
    assert key.startswith("v1:type_text:")
    assert "segredo" not in key
    assert journal.transitions == ["in_flight", "executed"]
    assert journal.receipt == {"action": "type_text", "verified": True, "characters": 5}
    assert "segredo" not in repr(journal.receipt)
    assert result["journal_action_key"] == key


def test_in_flight_non_idempotent_action_is_fail_closed_without_physical_replay() -> None:
    physical = _PhysicalExecutor()
    journal = _FakeJournal("in_flight")
    guarded = LeaseGuardedExecutor(physical, _Heartbeat(), journal=journal)  # type: ignore[arg-type]

    with pytest.raises(ActionReplayBlocked, match="replay físico cego"):
        guarded.execute(Plan("type_text", "não repetir"))

    assert physical.calls == 0
    assert journal.transitions == []


def test_executed_non_idempotent_action_is_not_replayed_and_returns_safe_receipt() -> None:
    physical = _PhysicalExecutor()
    journal = _FakeJournal(
        "executed",
        {"action": "type_text", "verified": True, "characters": 5},
    )
    guarded = LeaseGuardedExecutor(physical, _Heartbeat(), journal=journal)  # type: ignore[arg-type]

    result = guarded.execute(Plan("type_text", "não repetir"))

    assert physical.calls == 0
    assert result["journal_recovered"] is True
    assert result["characters"] == 5


def test_repeat_safe_action_may_reexecute_after_in_flight_recovery() -> None:
    physical = _PhysicalExecutor({"action": "active_window", "verified": True})
    journal = _FakeJournal("in_flight")
    guarded = LeaseGuardedExecutor(physical, _Heartbeat(), journal=journal)  # type: ignore[arg-type]

    guarded.execute(Plan("active_window", "active"))

    assert physical.calls == 1
    assert journal.transitions == ["in_flight", "executed"]


def test_repeat_safe_executed_action_may_be_observed_again_without_state_regression() -> None:
    physical = _PhysicalExecutor({"action": "active_window", "verified": True})
    journal = _FakeJournal("executed", {"action": "active_window", "verified": True})
    guarded = LeaseGuardedExecutor(physical, _Heartbeat(), journal=journal)  # type: ignore[arg-type]

    guarded.execute(Plan("active_window", "active"))

    assert physical.calls == 1
    assert journal.transitions == ["executed"]


def test_same_non_idempotent_action_is_deduplicated_within_the_same_task() -> None:
    target = "mesmo texto"
    first_journal = _FakeJournal("prepared")
    first = LeaseGuardedExecutor(_PhysicalExecutor(), _Heartbeat(), journal=first_journal)  # type: ignore[arg-type]
    first.execute(Plan("type_text", target))

    second_journal = _FakeJournal("executed", {"action": "type_text", "verified": True})
    second_physical = _PhysicalExecutor()
    second = LeaseGuardedExecutor(second_physical, _Heartbeat(), journal=second_journal)  # type: ignore[arg-type]
    second.execute(Plan("type_text", target))

    assert first_journal.prepared_keys == second_journal.prepared_keys
    assert second_physical.calls == 0


def test_action_key_distinguishes_different_targets_without_storing_them() -> None:
    first_journal = _FakeJournal("prepared")
    first = LeaseGuardedExecutor(_PhysicalExecutor(), _Heartbeat(), journal=first_journal)  # type: ignore[arg-type]
    first.execute(Plan("type_text", "texto alfa"))

    second_journal = _FakeJournal("prepared")
    second = LeaseGuardedExecutor(_PhysicalExecutor(), _Heartbeat(), journal=second_journal)  # type: ignore[arg-type]
    second.execute(Plan("type_text", "texto beta"))

    first_key = first_journal.prepared_keys[0]
    second_key = second_journal.prepared_keys[0]
    assert first_key != second_key
    assert "alfa" not in first_key
    assert "beta" not in second_key
