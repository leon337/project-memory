from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from context_anchor.fault_injection import FAULT_EXIT_CODE, FaultInjectionController
from context_anchor.lease import LeaseGuardedExecutor
from context_anchor.policy import Plan


class _Heartbeat:
    task_id = "task-fault-1"
    lease_token = "t" * 24

    def assert_owned(self) -> None:
        return None


class _PhysicalExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, _: Plan) -> dict[str, Any]:
        self.calls += 1
        return {"action": "type_text", "verified": True, "characters": 4}


class _Journal:
    def __init__(self) -> None:
        self.state = "prepared"
        self.transitions: list[str] = []

    def prepare(self, **_: Any) -> dict[str, Any]:
        return {"state": self.state, "receipt": None}

    def transition(self, *, state: str, **_: Any) -> dict[str, Any]:
        self.state = state
        self.transitions.append(state)
        return {"state": state}


class _InjectedCrash(RuntimeError):
    pass


class _CrashAt:
    def __init__(self, checkpoint: str) -> None:
        self.checkpoint_name = checkpoint
        self.seen: list[str] = []

    def checkpoint(self, checkpoint: str, **_: Any) -> bool:
        self.seen.append(checkpoint)
        if checkpoint == self.checkpoint_name:
            raise _InjectedCrash(checkpoint)
        return False


def test_fault_arm_is_consumed_once_and_persists_only_safe_context(tmp_path: Path) -> None:
    exits: list[int] = []
    arm_path = tmp_path / "fault.json"
    last_path = tmp_path / "fault-last.json"
    controller = FaultInjectionController(
        arm_path,
        last_path,
        terminator=exits.append,
    )

    controller.arm("after_backend")
    assert controller.status()["checkpoint"] == "after_backend"  # type: ignore[index]
    assert controller.checkpoint("after_prepare") is False
    assert arm_path.exists()

    triggered = controller.checkpoint(
        "after_backend",
        context={
            "task_id": "task-1",
            "action_key": "v1:type_text:abc",
            "action_name": "type_text",
            "target": "segredo que não pode persistir",
        },
    )

    assert triggered is True
    assert exits == [FAULT_EXIT_CODE]
    assert not arm_path.exists()
    event = json.loads(last_path.read_text(encoding="utf-8"))
    assert event["checkpoint"] == "after_backend"
    assert event["context"] == {
        "task_id": "task-1",
        "action_key": "v1:type_text:abc",
        "action_name": "type_text",
    }
    assert "segredo" not in last_path.read_text(encoding="utf-8")

    assert controller.checkpoint("after_backend") is False
    assert exits == [FAULT_EXIT_CODE]


def test_crash_after_prepare_keeps_backend_unentered() -> None:
    physical = _PhysicalExecutor()
    journal = _Journal()
    crash = _CrashAt("after_prepare")
    guarded = LeaseGuardedExecutor(
        physical,
        _Heartbeat(),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        fault_injection=crash,  # type: ignore[arg-type]
    )

    with pytest.raises(_InjectedCrash, match="after_prepare"):
        guarded.execute(Plan("type_text", "teste"))

    assert physical.calls == 0
    assert journal.state == "prepared"
    assert journal.transitions == []


def test_crash_after_backend_leaves_in_flight_and_records_one_real_call() -> None:
    physical = _PhysicalExecutor()
    journal = _Journal()
    crash = _CrashAt("after_backend")
    guarded = LeaseGuardedExecutor(
        physical,
        _Heartbeat(),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        fault_injection=crash,  # type: ignore[arg-type]
    )

    with pytest.raises(_InjectedCrash, match="after_backend"):
        guarded.execute(Plan("type_text", "teste"))

    assert physical.calls == 1
    assert journal.state == "in_flight"
    assert journal.transitions == ["in_flight"]
    assert crash.seen == ["after_prepare", "after_in_flight", "after_backend"]


def test_normal_execution_exposes_all_executor_checkpoints_in_order() -> None:
    physical = _PhysicalExecutor()
    journal = _Journal()
    recorder = _CrashAt("never")
    guarded = LeaseGuardedExecutor(
        physical,
        _Heartbeat(),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        fault_injection=recorder,  # type: ignore[arg-type]
    )

    guarded.execute(Plan("type_text", "teste"))

    assert physical.calls == 1
    assert journal.transitions == ["in_flight", "executed"]
    assert recorder.seen == [
        "after_prepare",
        "after_in_flight",
        "after_backend",
        "after_executed",
    ]
