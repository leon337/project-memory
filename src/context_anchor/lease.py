from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

import httpx

from .desktop import DesktopFailsafeTriggered
from .emergency_stop import EmergencyStopTriggered
from .schemas import AgentLeaseView
from .session_context import ArtifactKind, ContextArtifact, ContextResolution, SessionContext


class LeaseOwnershipLost(RuntimeError):
    """Raised when the agent can no longer prove ownership of a running task."""


def is_safety_interrupt(exc: BaseException) -> bool:
    """Classify controls that must cross every retry/fallback boundary."""

    if isinstance(
        exc,
        (LeaseOwnershipLost, EmergencyStopTriggered, DesktopFailsafeTriggered),
    ):
        return True
    exc_type = type(exc)
    return (
        exc_type.__name__ == "FailSafeException"
        and exc_type.__module__.split(".", 1)[0] == "pyautogui"
    )


class LeaseHeartbeat:
    """Renew one task lease in the background and expose fail-closed checks.

    The heartbeat owns its HTTP client.  It deliberately does not share the
    polling/result client used by the local agent, so a slow request in either
    path cannot serialize all lease renewals behind the other path.
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
    """Proxy that verifies lease ownership around actions and observations."""

    def __init__(self, executor: Any, heartbeat: LeaseHeartbeat) -> None:
        self._executor = executor
        self._heartbeat = heartbeat

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
            # enter a fallback.  Existing safety controls retain priority.
            if self._must_preserve(exc):
                raise
            self.assert_authorized()
            raise
        self.assert_authorized()
        return result

    def execute(self, plan: Any) -> dict[str, Any]:
        return self._guarded_call(self._executor.execute, plan)

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
