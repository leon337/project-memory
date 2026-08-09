from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import context_anchor.goal_execution as goal_execution_module
import context_anchor.local_agent as local_agent_module
from context_anchor.desktop import DesktopFailsafeTriggered
from context_anchor.lease import (
    DeferredSessionContext,
    LeaseGuardedExecutor,
    LeaseHeartbeat,
    LeaseOwnershipLost,
)
from context_anchor.local_agent import _submit_task_result, execute_command
from context_anchor.policy import Plan
from context_anchor.session_context import ArtifactKind, SessionContext


def _client_factory(handler: Any) -> Any:
    transport = httpx.MockTransport(handler)
    return lambda: httpx.Client(base_url="http://central.test", transport=transport)


def test_heartbeat_confirms_ownership_immediately_with_its_own_client() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        expires = datetime.now(timezone.utc) + timedelta(minutes=2)
        return httpx.Response(
            200,
            json={"id": "task-1", "lease_expires_at": expires.isoformat()},
        )

    with LeaseHeartbeat(
        base_url="http://unused.test",
        headers={"Authorization": "Bearer agent-token"},
        task_id="task-1",
        lease_token="t" * 24,
        lease_seconds=120,
        client_factory=_client_factory(handler),
    ) as heartbeat:
        heartbeat.assert_owned()

    assert len(calls) == 1
    assert calls[0].url.path == "/api/agent/tasks/task-1/lease"
    assert calls[0].method == "POST"


def test_heartbeat_fails_closed_when_central_rejects_renewal() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "lease expirado"})

    heartbeat = LeaseHeartbeat(
        base_url="http://unused.test",
        headers={},
        task_id="task-1",
        lease_token="t" * 24,
        lease_seconds=120,
        client_factory=_client_factory(handler),
    )

    with pytest.raises(LeaseOwnershipLost, match="renovação do lease falhou"):
        heartbeat.start()


def test_executor_checks_lease_before_physical_action() -> None:
    class LostHeartbeat:
        def assert_owned(self) -> None:
            raise LeaseOwnershipLost("lease perdido")

    class PhysicalExecutor:
        calls = 0

        def execute(self, _: Plan) -> dict[str, Any]:
            self.calls += 1
            return {"ok": True}

    physical = PhysicalExecutor()
    guarded = LeaseGuardedExecutor(physical, LostHeartbeat())  # type: ignore[arg-type]

    with pytest.raises(LeaseOwnershipLost, match="lease perdido"):
        guarded.execute(Plan("open_url", "https://example.com"))
    assert physical.calls == 0


def test_observation_failure_after_lease_loss_cannot_enter_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LosingHeartbeat:
        checks = 0

        def assert_owned(self) -> None:
            self.checks += 1
            if self.checks >= 4:
                raise LeaseOwnershipLost("lease perdido durante observação")

    class Executor:
        desktop_enabled = False

        def execute(self, _: Plan) -> dict[str, Any]:
            return {"verified": True}

        def observe_browser(self, **_: Any) -> dict[str, Any]:
            raise RuntimeError("observação falhou")

    guarded = LeaseGuardedExecutor(Executor(), LosingHeartbeat())  # type: ignore[arg-type]
    probe_calls = 0

    def forbidden_probe(_: str) -> dict[str, Any]:
        nonlocal probe_calls
        probe_calls += 1
        raise AssertionError("fallback HTTP não pode executar após perda de lease")

    monkeypatch.setattr(goal_execution_module, "_probe_url", forbidden_probe)
    command = (
        "Se example.com estiver acessível, abra um editor e escreva 'sim'; "
        "senão escreva 'não'."
    )
    with pytest.raises(LeaseOwnershipLost, match="durante observação"):
        execute_command(guarded, command)  # type: ignore[arg-type]
    assert probe_calls == 0


def test_lease_loss_propagates_through_goal_runtime_without_fallback() -> None:
    class LostExecutor:
        calls = 0
        desktop_enabled = False

        def execute(self, _: Plan) -> dict[str, Any]:
            self.calls += 1
            raise LeaseOwnershipLost("lease perdido")

    executor = LostExecutor()
    with pytest.raises(LeaseOwnershipLost, match="lease perdido"):
        execute_command(executor, "Abra o navegador e acesse o site example.com")  # type: ignore[arg-type]
    assert executor.calls == 1


def test_session_context_is_only_written_after_explicit_commit(tmp_path: Path) -> None:
    context = SessionContext(tmp_path / "session-context.json")
    deferred = DeferredSessionContext(context)
    deferred.remember_many(
        "task-1",
        {ArtifactKind.LOCATION: "São Lourenço da Mata"},
    )

    assert deferred.has_pending is True
    assert context.get(ArtifactKind.LOCATION) is None

    committed = deferred.commit()
    assert committed
    assert deferred.has_pending is False
    assert context.get(ArtifactKind.LOCATION) == "São Lourenço da Mata"


def test_deferred_session_context_can_discard_unacknowledged_result(tmp_path: Path) -> None:
    context = SessionContext(tmp_path / "session-context.json")
    deferred = DeferredSessionContext(context)
    deferred.remember_many("task-1", {ArtifactKind.SUBJECT: "resultado local"})
    deferred.discard()

    assert deferred.has_pending is False
    assert context.get(ArtifactKind.SUBJECT) is None


def test_rejected_result_never_commits_session_context(tmp_path: Path) -> None:
    context = SessionContext(tmp_path / "session-context.json")
    deferred = DeferredSessionContext(context)
    deferred.remember_many("task-1", {ArtifactKind.SUBJECT: "resultado local"})

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "lease expirado"})

    with httpx.Client(
        base_url="http://central.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            _submit_task_result(
                client,
                "task-1",
                {"lease_token": "t" * 24, "ok": True, "result": {}},
                deferred,
            )

    assert context.get(ArtifactKind.SUBJECT) is None
    assert deferred.has_pending is False


def test_accepted_success_commits_session_context(tmp_path: Path) -> None:
    context = SessionContext(tmp_path / "session-context.json")
    deferred = DeferredSessionContext(context)
    deferred.remember_many("task-1", {ArtifactKind.SUBJECT: "resultado aceito"})

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "task-1", "status": "succeeded"})

    with httpx.Client(
        base_url="http://central.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = _submit_task_result(
            client,
            "task-1",
            {"lease_token": "t" * 24, "ok": True, "result": {}},
            deferred,
        )

    assert result["status"] == "succeeded"
    assert context.get(ArtifactKind.SUBJECT) == "resultado aceito"
    assert deferred.has_pending is False


@pytest.mark.parametrize(
    ("lease_lost_at_final_check", "expected_post_calls", "interrupt_kind"),
    [
        (False, 1, "desktop"),
        (True, 0, "desktop"),
        (False, 1, "pyautogui"),
        (True, 0, "pyautogui"),
    ],
)
def test_desktop_failsafe_dominates_post_error_and_lease_loss(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    lease_lost_at_final_check: bool,
    expected_post_calls: int,
    interrupt_kind: str,
) -> None:
    class Response:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

        def raise_for_status(self) -> None:
            if self.status_code < 400:
                return
            request = httpx.Request("POST", "http://central.test/result")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "Central indisponível",
                request=request,
                response=response,
            )

    class MainClient:
        get_calls = 0
        post_calls = 0

        def __enter__(self) -> MainClient:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get(self, *_: Any, **__: Any) -> Response:
            self.get_calls += 1
            if self.get_calls > 1:
                raise AssertionError("Robô tentou obter uma segunda tarefa após failsafe")
            expires = datetime.now(timezone.utc) + timedelta(minutes=2)
            return Response(
                200,
                {
                    "id": "task-1",
                    "command": "abra example.com",
                    "lease_token": "t" * 24,
                    "lease_expires_at": expires.isoformat(),
                    "lease_seconds": 120,
                },
            )

        def post(self, *_: Any, **__: Any) -> Response:
            self.post_calls += 1
            return Response(503, {"detail": "indisponível"})

    class Stop:
        def __init__(self, *_: Any) -> None:
            pass

        def is_triggered(self) -> bool:
            return False

        def assert_not_triggered(self) -> None:
            return None

        @contextmanager
        def register_agent_process(self):
            yield

    class Executor:
        closed = False

        def close(self) -> None:
            self.closed = True

    class Heartbeat:
        def __init__(self, **_: Any) -> None:
            pass

        def __enter__(self) -> Heartbeat:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def assert_owned(self) -> None:
            if lease_lost_at_final_check:
                raise LeaseOwnershipLost("lease perdido no encerramento")
            return None

    cfg = SimpleNamespace(
        agent_token="a" * 32,
        emergency_stop_path=tmp_path / "stop",
        agent_pid_path=tmp_path / "agent.pid",
        browser_headless=True,
        desktop_enabled=False,
        screenshot_dir=tmp_path / "screens",
        session_context_path=tmp_path / "context.json",
        control_plane_url="http://central.test",
        agent_id="test-agent",
        goal_max_steps=8,
        poll_interval_seconds=0.5,
    )
    main_client = MainClient()
    executor = Executor()
    monkeypatch.setattr(local_agent_module, "LocalAgentSettings", lambda: cfg)
    monkeypatch.setattr(
        local_agent_module,
        "DashboardSettings",
        lambda: SimpleNamespace(log_dir=tmp_path / "logs"),
    )
    monkeypatch.setattr(local_agent_module, "EmergencyStop", Stop)
    monkeypatch.setattr(local_agent_module, "ActionExecutor", lambda **_: executor)
    monkeypatch.setattr(local_agent_module, "build_planner", lambda _: object())
    monkeypatch.setattr(local_agent_module, "LeaseHeartbeat", Heartbeat)
    monkeypatch.setattr(local_agent_module.httpx, "Client", lambda **_: main_client)
    monkeypatch.setattr(local_agent_module, "write_runtime_log", lambda *_, **__: None)
    monkeypatch.setattr(local_agent_module.time, "sleep", lambda _: None)

    def trigger_failsafe(*_: Any, **__: Any) -> dict[str, Any]:
        if interrupt_kind == "desktop":
            raise DesktopFailsafeTriggered("ponteiro no canto")
        native_type = type(
            "FailSafeException",
            (Exception,),
            {"__module__": "pyautogui"},
        )
        raise native_type("ponteiro no canto")

    monkeypatch.setattr(local_agent_module, "execute_command", trigger_failsafe)

    local_agent_module.run()

    assert main_client.get_calls == 1
    assert main_client.post_calls == expected_post_calls
    assert executor.closed is True
