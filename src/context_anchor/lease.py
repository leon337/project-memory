from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

import httpx

from .action_journal import ActionJournalClient, ActionReplayBlocked
from .desktop import DesktopFailsafeTriggered
from .emergency_stop import EmergencyStopTriggered
from .fault_injection import FaultInjectionController
from .schemas import AgentLeaseView
from .session_context import ArtifactKind, ContextArtifact, ContextResolution, SessionContext


class LeaseOwnershipLost(RuntimeError):
    """Raised when the agent can no longer prove ownership of a running task."""


def is_safety_interrupt(exc: BaseException) -> bool:
    """Classify controls that must cross every retry/fallback boundary."""

    if isinstance(
        exc,
        (
            LeaseOwnershipLost,
            ActionReplayBlocked,
            EmergencyStopTriggered,
            DesktopFailsafeTriggered,
        ),
    ):
        return True
    exc_type = type(exc)
    return (
        exc_type.__name__ == "FailSafeException"
        and exc_type.__module__.split(".", 1)[0] == "pyautogui"
    )


class LeaseHeartbeat:
    """Renew one task lease in the background and expose fail-closed checks.

    The heartbeat owns its HTTP client. It deliberately does not share the
    polling/result client used by the local agent, so a slow request in either
    path cannot serialize all lease renewals behind the other path. Journal
    calls create short-lived clients from the same authenticated factory.
    """

    def __init__(
        self,
        *,
        base_url: str,
        headers: Mapping[str, str],
        task_id: str,
        lease_token: str,
        lease_seconds: int,
        timeout_seconds: float = 10.0,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds deve ser positivo.")
        self.task_id = task_id
        self.lease_token = lease_token
        self.lease_seconds = lease_seconds
        self._interval_seconds = max(0.25, lease_seconds / 3)
        self._client_factory = client_factory or (
            lambda: httpx.Client(
                base_url=base_url,
                headers=dict(headers),
                timeout=timeout_seconds,
            )
        )
        self._timeout_seconds = timeout_seconds
        self._client: httpx.Client | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._lost: LeaseOwnershipLost | None = None
        self._lease_expires_at: datetime | None = None

    def new_client(self) -> httpx.Client:
        """Create an authenticated Central client without sharing thread state."""

        return self._client_factory()

    def start(self) -> LeaseHeartbeat:
        if self._client is not None:
            raise RuntimeError("Heartbeat de lease já iniciado.")
        self._client = self._client_factory()
        try:
            # Confirm ownership immediately, before the first physical action.
            self._renew_once()
        except Exception:
            self._client.close()
            self._client = None
            raise
        self._thread = threading.Thread(
            target=self._run,
            name=f"lease-heartbeat-{self.task_id[:12]}",
            daemon=True,
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=self._timeout_seconds + 1)
        client = self._client
        self._thread = None
        self._client = None
        if client is not None:
            client.close()

    def assert_owned(self) -> None:
        with self._lock:
            lost = self._lost
            expires_at = self._lease_expires_at
        if lost is not None:
            raise lost
        if expires_at is None or datetime.now(timezone.utc) >= expires_at:
            lost = self._mark_lost(
                "A posse da tarefa não pôde ser comprovada por um lease vigente."
            )
            raise lost

    def _mark_lost(self, message: str) -> LeaseOwnershipLost:
        with self._lock:
            if self._lost is None:
                self._lost = LeaseOwnershipLost(message)
            return self._lost

    def _renew_once(self) -> None:
        client = self._client
        if client is None:
            raise RuntimeError("Heartbeat de lease não iniciado.")
        try:
            response = client.post(
                f"/api/agent/tasks/{self.task_id}/lease",
                json={"lease_token": self.lease_token},
            )
            response.raise_for_status()
            renewed = AgentLeaseView.model_validate(response.json())
            if renewed.id != self.task_id:
                raise ValueError("A Central respondeu com outra tarefa.")
            expires_at = renewed.lease_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            expires_at = expires_at.astimezone(timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise ValueError("A Central respondeu com um lease já expirado.")
        except Exception as exc:
            lost = self._mark_lost(
                "A renovação do lease falhou; a execução perdeu autorização para agir "
                f"({type(exc).__name__})."
            )
            raise lost from exc
        with self._lock:
            self._lease_expires_at = expires_at

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self._renew_once()
            except LeaseOwnershipLost:
                return

    def __enter__(self) -> LeaseHeartbeat:
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.stop()


class LeaseGuardedExecutor:
    """Proxy that verifies lease ownership and durable replay state around actions."""

    _REPEAT_SAFE_ACTIONS = frozenset({"active_window", "capture_screen"})
    _SAFE_RECEIPT_FIELDS: dict[str, tuple[str, ...]] = {
        "open_url": ("action", "verified", "http_status"),
        "capture_screen": ("action", "verified"),
        "active_window": ("action", "verified"),
        "move_mouse": ("action", "verified", "x", "y"),
        "click_mouse": ("action", "verified", "button", "x", "y", "window_id"),
        "type_text": (
            "action",
            "verified",
            "characters",
            "input_method",
            "window_id",
        ),
        "press_key": ("action", "verified", "key", "window_id"),
        "open_app": (
            "action",
            "verified",
            "pid",
            "window_changed",
            "window_id",
        ),
    }

    def __init__(
        self,
        executor: Any,
        heartbeat: LeaseHeartbeat,
        journal: ActionJournalClient | None = None,
        fault_injection: FaultInjectionController | None = None,
    ) -> None:
        self._executor = executor
        self._heartbeat = heartbeat
        self._fault_injection = fault_injection
        if journal is not None:
            self._journal = journal
        elif all(
            hasattr(heartbeat, name)
            for name in ("task_id", "lease_token", "new_client")
        ):
            self._journal = ActionJournalClient(
                task_id=heartbeat.task_id,
                lease_token=heartbeat.lease_token,
                client_factory=heartbeat.new_client,
            )
        else:
            # Test doubles and legacy direct construction remain usable. The
            # production LocalAgent always supplies a real LeaseHeartbeat.
            self._journal = None

    @staticmethod
    def _must_preserve(exc: BaseException) -> bool:
        return is_safety_interrupt(exc)

    def assert_authorized(self) -> None:
        self._heartbeat.assert_owned()

    def _guarded_call(self, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self.assert_authorized()
        try:
            result = operation(*args, **kwargs)
        except Exception as exc:
            # If an observation/action fails after lease loss, propagate the
            # ownership interruption instead of letting Goal Runtime retry or
            # enter a fallback. Existing safety controls retain priority.
            if self._must_preserve(exc):
                raise
            self.assert_authorized()
            raise
        self.assert_authorized()
        return result

    def _action_key(self, action_name: str, target: str) -> str:
        """Build a task-scoped stable identity without persisting the raw target.

        A task UUID salts a compact BLAKE2 fingerprint, so identical target
        values from different tasks are not globally correlatable. The key has
        no retry/occurrence counter on purpose: the same non-repeat-safe
        action+target inside one task resolves to the same journal row, so a
        retry/reclaim cannot silently manufacture a second physical invocation.

        A future capability that *legitimately* needs two identical physical
        effects must provide a distinct stable contract-level identity instead
        of relying on an implicit retry counter.
        """

        task_id = str(getattr(self._heartbeat, "task_id", "legacy-task"))
        task_key = task_id.encode("utf-8")[:32] or b"legacy-task"
        raw_signature = f"{action_name}\0{target}".encode("utf-8")
        fingerprint = hashlib.blake2s(
            raw_signature,
            key=task_key,
            digest_size=12,
        ).hexdigest()
        return f"v1:{action_name}:{fingerprint}"

    @classmethod
    def _repeat_safe(cls, action_name: str) -> bool:
        return action_name in cls._REPEAT_SAFE_ACTIONS

    @classmethod
    def _safe_receipt(cls, action_name: str, receipt: dict[str, Any]) -> dict[str, Any]:
        allowed = cls._SAFE_RECEIPT_FIELDS.get(action_name, ("action", "verified"))
        return {key: receipt[key] for key in allowed if key in receipt}

    def _fault(self, checkpoint: str, *, action_key: str, action_name: str) -> None:
        controller = self._fault_injection
        if controller is None:
            return
        controller.checkpoint(
            checkpoint,
            context={
                "task_id": str(getattr(self._heartbeat, "task_id", "legacy-task")),
                "action_key": action_key,
                "action_name": action_name,
            },
        )

    def execute(self, plan: Any) -> dict[str, Any]:
        self.assert_authorized()
        journal = self._journal
        if journal is None:
            return self._guarded_call(self._executor.execute, plan)

        action_name = str(getattr(plan, "action", ""))
        target = str(getattr(plan, "target", ""))
        action_key = self._action_key(action_name, target)
        repeat_safe = self._repeat_safe(action_name)
        prepared = journal.prepare(
            action_key=action_key,
            action_name=action_name,
            repeat_safe=repeat_safe,
        )
        state = str(prepared.get("state") or "")

        if state == "executed" and not repeat_safe:
            receipt = prepared.get("receipt")
            recovered = dict(receipt) if isinstance(receipt, dict) else {}
            recovered.setdefault("action", action_name)
            recovered["journal_recovered"] = True
            recovered["journal_action_key"] = action_key
            return recovered

        if state == "acknowledged":
            raise ActionReplayBlocked(action_key, state)

        if state == "in_flight" and not repeat_safe:
            raise ActionReplayBlocked(action_key, state)

        if state not in {"prepared", "in_flight", "executed"}:
            raise ActionReplayBlocked(action_key, state or "unknown")

        if state == "prepared":
            self._fault("after_prepare", action_key=action_key, action_name=action_name)

        # PREPARED proves the backend was never entered. IN_FLIGHT/EXECUTED is
        # repeated only for explicitly repeat-safe observation-like actions.
        # An already EXECUTED repeat-safe action stays EXECUTED while the fresh
        # observation is performed; no unsafe state regression is required.
        if state != "executed":
            journal.transition(action_key=action_key, state="in_flight")
            self._fault("after_in_flight", action_key=action_key, action_name=action_name)
        try:
            result = self._guarded_call(self._executor.execute, plan)
        except Exception:
            # Deliberately leave IN_FLIGHT when backend entry was possible. A
            # crash/error there cannot prove whether an external effect occurred.
            raise
        self._fault("after_backend", action_key=action_key, action_name=action_name)
        safe_receipt = self._safe_receipt(action_name, result)
        journal.transition(
            action_key=action_key,
            state="executed",
            receipt=safe_receipt,
        )
        self._fault("after_executed", action_key=action_key, action_name=action_name)
        result = dict(result)
        result["journal_action_key"] = action_key
        return result

    def observe_browser(self, **kwargs: Any) -> dict[str, Any]:
        return self._guarded_call(self._executor.observe_browser, **kwargs)

    def observe_application(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._guarded_call(self._executor.observe_application, *args, **kwargs)

    def read_active_text(self, **kwargs: Any) -> dict[str, Any]:
        return self._guarded_call(self._executor.read_active_text, **kwargs)

    def observe_active_window(self) -> dict[str, Any]:
        return self._guarded_call(self._executor.observe_active_window)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._executor, name)


class DeferredSessionContext:
    """Read current context now, but persist new artifacts only after commit()."""

    def __init__(self, context: SessionContext) -> None:
        self._context = context
        self._pending: list[tuple[str, dict[ArtifactKind | str, str | None]]] = []

    def resolve_with_provenance(self, text: str) -> ContextResolution:
        return self._context.resolve_with_provenance(text)

    def remember_many(
        self,
        origin_task_id: str,
        artifacts: Mapping[ArtifactKind | str, str | None],
        **_: Any,
    ) -> tuple[ContextArtifact, ...]:
        self._pending.append((origin_task_id, dict(artifacts)))
        return ()

    def commit(self) -> tuple[ContextArtifact, ...]:
        recorded: list[ContextArtifact] = []
        for origin_task_id, artifacts in self._pending:
            recorded.extend(self._context.remember_many(origin_task_id, artifacts))
        self._pending.clear()
        return tuple(recorded)

    def discard(self) -> None:
        self._pending.clear()

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._context, name)


__all__ = [
    "DeferredSessionContext",
    "LeaseGuardedExecutor",
    "LeaseHeartbeat",
    "LeaseOwnershipLost",
    "is_safety_interrupt",
]
