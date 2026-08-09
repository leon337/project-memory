from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import context_anchor.goal_execution as goal_execution
import context_anchor.local_agent as local_agent
from context_anchor.goal_runtime import (
    CriterionCheck,
    EvidenceKind,
    EvidenceRecord,
    GoalContract,
    GoalCriterion,
    GoalRunState,
    GoalRunStatus,
    GoalStep,
    GoalStepStatus,
    GoalSubgoal,
    ProgressStatus,
)
from context_anchor.lease import DeferredSessionContext
from context_anchor.redaction import redact_text, redact_url
from context_anchor.session_context import ArtifactKind, SessionContext
from context_anchor.store import TaskStore


def test_url_redaction_removes_userinfo_path_query_and_fragment() -> None:
    value = (
        "https://alice:correct-horse@example.com:8443/people/alice/private.txt"
        "?token=query-secret&name=Alice#personal-fragment"
    )

    redacted = redact_url(value)

    assert redacted == "https://example.com:8443/[redacted-path]?[redacted]"
    for private_value in (
        "alice",
        "correct-horse",
        "people",
        "private.txt",
        "token",
        "query-secret",
        "personal-fragment",
    ):
        assert private_value not in redacted


@pytest.mark.parametrize(
    "private_value",
    [
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.private.signature",
        "Authorization: Basic dXNlcjpwcml2YXRlLXBhc3N3b3Jk",
        "Bearer opaque-access-token-123456",
        "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz",
        "AIzaSyD-abcdefghijklmnopqrstuvwxyz123456",
        "AKIAIOSFODNN7EXAMPLE",
        "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature123",
        "meu token opaquevalue123456",
        'API_KEY="quoted secret with spaces"',
        "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    ],
)
def test_credential_families_are_redacted(private_value: str) -> None:
    redacted = redact_text(f"falha do provedor: {private_value}")

    assert private_value not in redacted
    assert "[redacted" in redacted


def test_result_payload_has_no_correlatable_hash_or_private_write_content() -> None:
    private_text = "conteúdo pessoal sem marcador de segredo"
    bearer = "Bearer ultra-private-runtime-token"
    api_key = "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz"
    aws_key = "AKIAIOSFODNN7EXAMPLE"
    private_url = (
        "https://alice:password@example.com/private/customer-42"
        "?download=raw-query-secret#hidden"
    )
    criterion = GoalCriterion(
        id="text_present",
        description="texto relido",
        check=CriterionCheck.EQUALS,
        expected_value=private_text,
        status=ProgressStatus.SATISFIED,
        allowed_evidence_kinds=(EvidenceKind.READBACK,),
    )
    contract = GoalContract(
        original_goal=f"Abra o editor e escreva {private_text}",
        criteria=[criterion],
        subgoals=[
            GoalSubgoal(
                id="write",
                description="escrever",
                produces=["text_present"],
                status=ProgressStatus.SATISFIED,
            )
        ],
        artifacts={
            "branch_text": private_text,
            "private_url": private_url,
            "diagnostic": f"{bearer} {api_key} {aws_key}",
        },
    )
    run = GoalRunState(contract=contract, task_id="task-public")
    step = GoalStep(
        id="step-write",
        action_key=f"type_text:{private_text}",
        strategy="desktop.type-and-readback",
        status=GoalStepStatus.SUCCEEDED,
        made_progress=True,
        subgoal_id="write",
        error=f"diagnóstico {private_text} em {private_url}",
        metadata={
            "action": "type_text",
            "target": private_text,
            "receipt": {"characters": len(private_text), "requested_url": private_url},
        },
    )
    run.record_step(step)
    evidence = EvidenceRecord(
        id="evidence-readback",
        criterion_id="text_present",
        kind=EvidenceKind.READBACK,
        source="desktop.atspi",
        verified=True,
        observed_value=private_text,
        step_id=step.id,
    )
    run.record_evidence(evidence)
    run.status = GoalRunStatus.SUCCEEDED

    result = goal_execution._result_payload(
        run,
        f"concluído: {private_text}",
        resolved_goal=f"Abra o editor e escreva {private_text}",
        resolution=None,
    )
    serialized = json.dumps(result, ensure_ascii=False)

    for private_value in (
        private_text,
        "alice",
        "password",
        "private/customer-42",
        "download",
        "raw-query-secret",
        bearer,
        api_key,
        aws_key,
    ):
        assert private_value not in serialized
    assert "fingerprint" not in serialized
    assert result["steps"][0]["target"] == {
        "redacted": True,
        "characters": len(private_text),
    }
    assert result["original_goal"].startswith("[redacted goal;")


def test_session_context_refuses_or_skips_sensitive_artifacts(tmp_path: Path) -> None:
    path = tmp_path / "session-context.json"
    context = SessionContext(path)
    secret = "API_KEY=context-secret-value"

    recorded = context.remember_many(
        "task-1",
        {
            ArtifactKind.SUBJECT: secret,
            ArtifactKind.SITE: "example.com",
            ArtifactKind.RESULT: "Bearer result-secret-token",
        },
    )

    assert [item.kind for item in recorded] == [ArtifactKind.SITE]
    assert context.last_subject is None
    assert context.last_result is None
    assert context.last_site == "example.com"
    assert "context-secret-value" not in path.read_text(encoding="utf-8")
    assert "result-secret-token" not in path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="sensitive context artifact"):
        context.remember(ArtifactKind.SUBJECT, secret, "task-2")


def test_legacy_sensitive_context_is_not_loaded(tmp_path: Path) -> None:
    path = tmp_path / "session-context.json"
    timestamp = datetime.now(timezone.utc).isoformat()
    path.write_text(
        json.dumps(
            [
                {
                    "kind": "subject",
                    "value": "sk-proj-legacy-secret-123456789",
                    "origin_task_id": "task-old",
                    "timestamp": timestamp,
                }
            ]
        ),
        encoding="utf-8",
    )

    context = SessionContext(path)

    assert context.artifacts == ()


def test_goal_context_filter_never_queues_secret_query(tmp_path: Path) -> None:
    context = SessionContext(tmp_path / "session-context.json")
    deferred = DeferredSessionContext(context)
    run = GoalRunState(
        GoalContract(original_goal="pesquisa", criteria=[]),
        task_id="task-query",
    )
    intent = SimpleNamespace(
        query="API_KEY=private-query-value",
        url="",
    )

    goal_execution._remember_context(deferred, run, intent)

    assert "private-query-value" not in repr(deferred._pending)


def test_task_store_sanitizes_result_and_error_at_persistence_boundary(
    tmp_path: Path,
) -> None:
    store = TaskStore(tmp_path / "tasks.db")
    created = store.create_task("objetivo público")
    claimed = store.claim_next("privacy-agent")
    assert claimed is not None
    private_url = "https://alice:password@example.com/private/path?token=query-secret"

    completed = store.complete_task(
        created["id"],
        lease_token=claimed["lease_token"],
        ok=False,
        result={
            "nested": [
                {"url": private_url},
                {"credential": "sk-proj-storesecret123456789"},
            ],
            "preserved": {"items": [1, 2, 3]},
        },
        error="API_KEY=store-error-secret",
    )

    assert completed is not None
    serialized = json.dumps(completed, ensure_ascii=False)
    for private_value in (
        "alice",
        "password",
        "private/path",
        "query-secret",
        "sk-proj-storesecret123456789",
        "store-error-secret",
    ):
        assert private_value not in serialized
        assert private_value.encode() not in (tmp_path / "tasks.db").read_bytes()
    assert completed["result"]["preserved"] == {"items": [1, 2, 3]}
    assert completed["error"] == "API_KEY=[redacted]"


def test_local_agent_never_sends_or_logs_raw_exception_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    secret = "agent-exception-secret"
    api_key = "sk-proj-agentexception1234567890"
    private_url = "https://alice:password@example.com/private/path?token=query-secret"
    exception_message = (
        f"API_KEY={secret} Authorization: Bearer bearer-secret-token "
        f"{api_key} {private_url}"
    )

    class Response:
        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self._payload = payload

        def json(self) -> dict[str, Any]:
            return self._payload

        def raise_for_status(self) -> None:
            return None

    class MainClient:
        get_calls = 0
        submitted: list[dict[str, Any]] = []

        def __enter__(self) -> MainClient:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def get(self, *_: Any, **__: Any) -> Response:
            self.get_calls += 1
            if self.get_calls > 1:
                raise KeyboardInterrupt
            return Response(
                200,
                {
                    "id": "task-privacy",
                    "command": "execute uma tarefa",
                    "lease_token": "t" * 24,
                    "lease_expires_at": (
                        datetime.now(timezone.utc) + timedelta(minutes=2)
                    ).isoformat(),
                    "lease_seconds": 120,
                },
            )

        def post(self, *_: Any, **kwargs: Any) -> Response:
            self.submitted.append(kwargs["json"])
            return Response(200, {"id": "task-privacy", "status": "failed"})

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
        desktop_enabled = False

        def close(self) -> None:
            return None

    class Heartbeat:
        def __init__(self, **_: Any) -> None:
            pass

        def __enter__(self) -> Heartbeat:
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def assert_owned(self) -> None:
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
        agent_id="privacy-agent",
        goal_max_steps=8,
        poll_interval_seconds=0.1,
    )
    client = MainClient()
    logs: list[str] = []
    monkeypatch.setattr(local_agent, "LocalAgentSettings", lambda: cfg)
    monkeypatch.setattr(
        local_agent,
        "DashboardSettings",
        lambda: SimpleNamespace(log_dir=tmp_path / "logs"),
    )
    monkeypatch.setattr(local_agent, "EmergencyStop", Stop)
    monkeypatch.setattr(local_agent, "ActionExecutor", lambda **_: Executor())
    monkeypatch.setattr(local_agent, "build_planner", lambda _: object())
    monkeypatch.setattr(local_agent, "LeaseHeartbeat", Heartbeat)
    monkeypatch.setattr(local_agent.httpx, "Client", lambda **_: client)
    monkeypatch.setattr(
        local_agent,
        "write_runtime_log",
        lambda _component, message, **_: logs.append(message),
    )
    monkeypatch.setattr(
        local_agent,
        "execute_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError(exception_message)
        ),
    )

    local_agent.run()

    published = json.dumps(client.submitted, ensure_ascii=False)
    logged = "\n".join(logs)
    for private_value in (
        secret,
        "bearer-secret-token",
        api_key,
        "alice",
        "password",
        "private/path",
        "query-secret",
    ):
        assert private_value not in published
        assert private_value not in logged
    assert "[redacted" in published
    assert "[redacted" in logged
