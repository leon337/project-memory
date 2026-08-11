from __future__ import annotations

from typing import Any

import pytest

import context_anchor.lease as lease_module
import context_anchor.recovery_observation as recovery_observation
from context_anchor.capabilities import ResolvedCapability
from context_anchor.lease import LeaseGuardedExecutor
from context_anchor.local_agent import execute_command
from context_anchor.policy import Plan


class _Heartbeat:
    task_id = "task-recovery-executed"
    lease_token = "lease-token"

    def assert_owned(self) -> None:
        return None


class _ExecutedJournal:
    def __init__(self) -> None:
        self.prepare_calls: list[dict[str, Any]] = []

    def prepare(self, **kwargs: Any) -> dict[str, Any]:
        self.prepare_calls.append(dict(kwargs))
        return {
            "state": "executed",
            "receipt": {
                "action": "open_app",
                "verified": True,
                "pid": 4242,
                "window_changed": True,
                "window_id": "old-window",
            },
        }


class _Executor:
    desktop_enabled = True

    def __init__(self) -> None:
        self.physical_execute_calls: list[Plan] = []
        self.application_observer_calls = 0

    def execute(self, plan: Plan) -> dict[str, Any]:
        self.physical_execute_calls.append(plan)
        raise AssertionError("open_app recuperado de EXECUTED não pode ser reemitido")

    def observe_application(
        self,
        app_id: str,
        *,
        pid: int | None = None,
        expected_argument: str | None = None,
    ) -> dict[str, Any]:
        del app_id, pid, expected_argument
        self.application_observer_calls += 1
        return {
            "action": "observe_application",
            "window_id": "panel-window",
            "window_title": "Painel do Robô",
            "window_class": "brave-browser Brave-browser",
            "class_identity_observed": False,
            "identity_observed": False,
            "verified": False,
        }


class _Resolver:
    def resolve(
        self,
        capability: str,
        hint: str | None = None,
        *,
        strict_hint: bool = False,
    ) -> ResolvedCapability:
        del hint, strict_hint
        assert capability == "text.edit"
        return ResolvedCapability(
            capability="text.edit",
            app_id="xed",
            display_name="Xed",
            executable="/usr/bin/xed",
            argv=("--new-window",),
            source="test",
            startup_wm_class="xed",
        )


def _existing_xed_observation() -> dict[str, Any]:
    return {
        "action": "observe_application",
        "app": "xed",
        "window_id": str(int("0x4200007", 16)),
        "window_title": "Documento não-salvo 1",
        "window_class": "xed Xed",
        "window_process_id": 7001,
        "window_process_executable": "/usr/bin/xed",
        "process_alive": True,
        "process_identity_observed": True,
        "class_identity_observed": True,
        "identity_observed": True,
        "active_window": False,
        "recovery_existing_window": True,
        "observation_method": "x11-managed-window-class",
        "source": "x11-recovery",
        "verified": True,
    }


def _recovered_guard(monkeypatch) -> tuple[_Executor, _ExecutedJournal, LeaseGuardedExecutor]:
    executor = _Executor()
    journal = _ExecutedJournal()
    guarded = LeaseGuardedExecutor(
        executor,
        _Heartbeat(),
        journal=journal,  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        lease_module,
        "observe_existing_application",
        lambda app_id: _existing_xed_observation() if app_id == "xed" else {},
    )
    return executor, journal, guarded


def test_executed_open_app_recovery_uses_passive_existing_window_without_replay(
    monkeypatch,
) -> None:
    executor, journal, guarded = _recovered_guard(monkeypatch)

    result = execute_command(
        guarded,
        "Abra o editor de texto",
        capability_resolver=_Resolver(),
    )

    assert result["status"] == "succeeded"
    assert result["goal_completed"] is True
    assert executor.physical_execute_calls == []
    assert executor.application_observer_calls >= 1
    assert len(journal.prepare_calls) == 1
    assert journal.prepare_calls[0]["action_name"] == "open_app"
    observations = [
        item
        for item in result["evidence"]
        if item["kind"] == "observation"
    ]
    assert observations
    assert observations[-1]["verified"] is True
    assert observations[-1]["source"] == "desktop.x11_proc"


def test_recovered_inactive_window_does_not_authorize_keyboard_to_active_panel(
    monkeypatch,
) -> None:
    executor, journal, guarded = _recovered_guard(monkeypatch)
    result = execute_command(
        guarded,
        "Abra o editor de texto",
        capability_resolver=_Resolver(),
    )
    assert result["status"] == "succeeded"
    assert len(journal.prepare_calls) == 1

    monkeypatch.setattr(lease_module, "active_window_id", lambda: "999999")
    with pytest.raises(RuntimeError, match="não está com foco"):
        guarded.execute(Plan("type_text", "não pode ir para o Painel"))

    assert len(journal.prepare_calls) == 1
    assert executor.physical_execute_calls == []


def test_passive_recovery_observation_finds_inactive_matching_window(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        recovery_observation,
        "_managed_window_ids",
        lambda: ("0x5000002", "0x4200007"),
    )
    monkeypatch.setattr(
        recovery_observation,
        "_window_class",
        lambda window_id: (
            "brave-browser Brave-browser"
            if window_id == "0x5000002"
            else "xed Xed"
        ),
    )
    monkeypatch.setattr(
        recovery_observation,
        "_window_title",
        lambda window_id: (
            "Painel do Robô" if window_id == "0x5000002" else "Documento não-salvo 1"
        ),
    )
    monkeypatch.setattr(
        recovery_observation,
        "_window_process_id",
        lambda window_id: 6000 if window_id == "0x5000002" else 7001,
    )
    monkeypatch.setattr(
        recovery_observation,
        "_process_executable",
        lambda pid: "/usr/bin/brave-browser" if pid == 6000 else "/usr/bin/xed",
    )
    monkeypatch.setattr(
        recovery_observation,
        "active_window_id",
        lambda: str(int("0x5000002", 16)),
    )

    observed = recovery_observation.observe_existing_application("xed")

    assert observed["verified"] is True
    assert observed["window_id"] == str(int("0x4200007", 16))
    assert observed["window_class"] == "xed Xed"
    assert observed["active_window"] is False
    assert observed["recovery_existing_window"] is True
