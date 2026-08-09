"""Short, typed operational context shared between independent tasks.

This module deliberately stores referable artifacts instead of conversation
turns.  It is therefore suitable for resolving a small number of follow-up
references without turning the task database into a chat-history store.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import fcntl

from .redaction import contains_sensitive_data


class ArtifactKind(str, Enum):
    """Artifact categories that a later task is allowed to reference."""

    SUBJECT = "subject"
    LOCATION = "location"
    SITE = "site"
    BROWSER = "browser"
    EDITOR = "editor"
    RESULT = "result"


@dataclass(frozen=True, slots=True)
class ContextArtifact:
    """One bounded, referable value and its task-level provenance."""

    kind: ArtifactKind
    value: str
    origin_task_id: str
    timestamp: datetime

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind.value,
            "value": self.value,
            "origin_task_id": self.origin_task_id,
            "timestamp": _as_utc(self.timestamp).isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ContextArtifact:
        expected_fields = {"kind", "value", "origin_task_id", "timestamp"}
        if set(payload) != expected_fields:
            raise ValueError("context artifact has unsupported fields")

        value = payload["value"]
        origin_task_id = payload["origin_task_id"]
        raw_timestamp = payload["timestamp"]
        if not isinstance(value, str) or not isinstance(origin_task_id, str):
            raise ValueError("context artifact values must be strings")
        if not isinstance(raw_timestamp, str):
            raise ValueError("context artifact timestamp must be an ISO string")

        timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        return cls(
            kind=ArtifactKind(payload["kind"]),
            value=value,
            origin_task_id=origin_task_id,
            timestamp=_as_utc(timestamp),
        )


@dataclass(frozen=True, slots=True)
class ContextResolution:
    """Resolved command plus the exact artifacts used to resolve it."""

    original_text: str
    resolved_text: str
    artifacts: tuple[ContextArtifact, ...] = ()

    @property
    def changed(self) -> bool:
        return self.original_text != self.resolved_text


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SessionContext:
    """A bounded JSON-backed store for short operational context.

    The on-disk representation is intentionally only a JSON array of
    :class:`ContextArtifact` objects.  Writes use ``os.replace`` so readers see
    either the previous complete document or the next complete document.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        max_artifacts: int = 32,
        max_age: timedelta = timedelta(hours=24),
        max_bytes: int = 64 * 1024,
        max_value_chars: int = 2_048,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if max_artifacts <= 0:
            raise ValueError("max_artifacts must be greater than zero")
        if max_age <= timedelta(0):
            raise ValueError("max_age must be greater than zero")
        if max_bytes <= 2:
            raise ValueError("max_bytes must be large enough for a JSON array")
        if max_value_chars <= 0:
            raise ValueError("max_value_chars must be greater than zero")

        self.path = Path(path)
        self.max_artifacts = max_artifacts
        self.max_age = max_age
        self.max_bytes = max_bytes
        self.max_value_chars = max_value_chars
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._artifacts = self._read()
        self._artifacts = self._apply_limits(self._artifacts, reject_oversized=False)

    @property
    def artifacts(self) -> tuple[ContextArtifact, ...]:
        """Return a chronological, immutable snapshot of live artifacts."""

        self.prune()
        return tuple(self._artifacts)

    def remember(
        self,
        kind: ArtifactKind | str,
        value: str,
        origin_task_id: str,
        *,
        timestamp: datetime | None = None,
    ) -> ContextArtifact:
        """Persist one referable artifact and return its typed representation."""

        artifact_kind = ArtifactKind(kind)
        clean_value = self._validate_text(value, "value", self.max_value_chars)
        clean_origin = self._validate_text(origin_task_id, "origin_task_id", 256)
        if contains_sensitive_data(clean_value):
            raise ValueError("sensitive context artifact cannot be persisted")
        if contains_sensitive_data(clean_origin):
            raise ValueError("sensitive context origin cannot be persisted")
        artifact = ContextArtifact(
            kind=artifact_kind,
            value=clean_value,
            origin_task_id=clean_origin,
            timestamp=_as_utc(timestamp or self._clock()),
        )
        with self._exclusive_lock():
            self._artifacts = self._apply_limits(
                self._read(), reject_oversized=False
            )
            self._artifacts = self._apply_limits(
                [*self._artifacts, artifact], reject_oversized=True
            )
            self._write()
        return artifact

    def remember_many(
        self,
        origin_task_id: str,
        artifacts: Mapping[ArtifactKind | str, str | None],
        *,
        timestamp: datetime | None = None,
    ) -> tuple[ContextArtifact, ...]:
        """Persist several artifacts from one task in a single atomic write."""

        clean_origin = self._validate_text(origin_task_id, "origin_task_id", 256)
        if contains_sensitive_data(clean_origin):
            raise ValueError("sensitive context origin cannot be persisted")
        recorded_at = _as_utc(timestamp or self._clock())
        additions: list[ContextArtifact] = []
        for raw_kind, raw_value in artifacts.items():
            if raw_value is None:
                continue
            clean_value = self._validate_text(
                raw_value, "value", self.max_value_chars
            )
            if contains_sensitive_data(clean_value):
                continue
            additions.append(
                ContextArtifact(
                    kind=ArtifactKind(raw_kind),
                    value=clean_value,
                    origin_task_id=clean_origin,
                    timestamp=recorded_at,
                )
            )
        if not additions:
            return ()

        with self._exclusive_lock():
            self._artifacts = self._apply_limits(
                self._read(), reject_oversized=False
            )
            self._artifacts = self._apply_limits(
                [*self._artifacts, *additions], reject_oversized=True
            )
            self._write()
        return tuple(additions)

    def latest(self, kind: ArtifactKind | str) -> ContextArtifact | None:
        """Return the newest live artifact of ``kind``, including provenance."""

        artifact_kind = ArtifactKind(kind)
        self.prune()
        return next(
            (
                artifact
                for artifact in reversed(self._artifacts)
                if artifact.kind is artifact_kind
            ),
            None,
        )

    def get(self, kind: ArtifactKind | str) -> str | None:
        artifact = self.latest(kind)
        return artifact.value if artifact is not None else None

    @property
    def last_subject(self) -> str | None:
        return self.get(ArtifactKind.SUBJECT)

    @property
    def last_location(self) -> str | None:
        return self.get(ArtifactKind.LOCATION)

    @property
    def last_site(self) -> str | None:
        return self.get(ArtifactKind.SITE)

    @property
    def last_browser(self) -> str | None:
        return self.get(ArtifactKind.BROWSER)

    @property
    def last_editor(self) -> str | None:
        return self.get(ArtifactKind.EDITOR)

    @property
    def last_result(self) -> str | None:
        return self.get(ArtifactKind.RESULT)

    def resolve(self, text: str) -> str:
        """Resolve supported PT-BR references and return a planner-ready command."""

        return self.resolve_with_provenance(text).resolved_text

    def resolve_references(self, text: str) -> str:
        """Readable alias for :meth:`resolve`."""

        return self.resolve(text)

    def resolve_with_provenance(self, text: str) -> ContextResolution:
        """Resolve references while retaining which typed artifacts were used."""

        if not isinstance(text, str):
            raise TypeError("text must be a string")

        resolved = text
        used: list[ContextArtifact] = []
        explicit_patterns: tuple[tuple[ArtifactKind, str], ...] = (
            (ArtifactKind.BROWSER, r"\b(?:nesse|neste|naquele)\s+navegador\b"),
            (ArtifactKind.SITE, r"\b(?:nesse|neste|naquele)\s+site\b"),
            (ArtifactKind.EDITOR, r"\b(?:nesse|neste|naquele)\s+editor\b"),
            (ArtifactKind.RESULT, r"\b(?:esse|este|aquele)\s+resultado\b"),
            (ArtifactKind.SUBJECT, r"\b(?:esse|este|aquele)\s+assunto\b"),
        )
        for kind, pattern in explicit_patterns:
            resolved = self._replace_reference(resolved, pattern, kind, used)

        # In operational commands, Portuguese "lá" most often points to the
        # last location.  Site and subject are safe typed fallbacks when a
        # dedicated location was not extracted by the previous task.
        if re.search(r"\blá\b", resolved, flags=re.IGNORECASE):
            target = self._latest_of(
                ArtifactKind.LOCATION, ArtifactKind.SITE, ArtifactKind.SUBJECT
            )
            if target is not None:
                resolved = re.sub(
                    r"\blá\b", lambda _: target.value, resolved, flags=re.IGNORECASE
                )
                used.append(target)

        unique_used: list[ContextArtifact] = []
        for artifact in used:
            if artifact not in unique_used:
                unique_used.append(artifact)
        return ContextResolution(text, resolved, tuple(unique_used))

    def prune(self) -> int:
        """Remove expired/excess artifacts, persisting only when state changed."""

        bounded = self._apply_limits(self._artifacts, reject_oversized=False)
        removed = len(self._artifacts) - len(bounded)
        if bounded != self._artifacts:
            self._artifacts = bounded
            if self.path.exists() or self._artifacts:
                self._write()
        return removed

    def reload(self) -> tuple[ContextArtifact, ...]:
        """Reload the store after another process may have updated it."""

        self._artifacts = self._apply_limits(self._read(), reject_oversized=False)
        return tuple(self._artifacts)

    def _latest_of(self, *kinds: ArtifactKind) -> ContextArtifact | None:
        self.prune()
        for kind in kinds:
            artifact = next(
                (
                    item
                    for item in reversed(self._artifacts)
                    if item.kind is kind
                ),
                None,
            )
            if artifact is not None:
                return artifact
        return None

    def _replace_reference(
        self,
        text: str,
        pattern: str,
        kind: ArtifactKind,
        used: list[ContextArtifact],
    ) -> str:
        if not re.search(pattern, text, flags=re.IGNORECASE):
            return text
        artifact = self._latest_of(kind)
        if artifact is None:
            return text
        used.append(artifact)
        return re.sub(pattern, lambda _: artifact.value, text, flags=re.IGNORECASE)

    def _apply_limits(
        self,
        artifacts: list[ContextArtifact],
        *,
        reject_oversized: bool,
    ) -> list[ContextArtifact]:
        cutoff = _as_utc(self._clock()) - self.max_age
        bounded = [item for item in artifacts if item.timestamp >= cutoff]
        bounded.sort(key=lambda item: item.timestamp)
        bounded = bounded[-self.max_artifacts :]

        while bounded and len(self._encode(bounded)) > self.max_bytes:
            if len(bounded) == 1 and reject_oversized:
                raise ValueError("context artifact exceeds max_bytes")
            bounded.pop(0)
        return bounded

    def _read(self) -> list[ContextArtifact]:
        if not self.path.exists():
            return []
        try:
            if self.path.stat().st_size > self.max_bytes:
                return []
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []

        artifacts: list[ContextArtifact] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                artifact = ContextArtifact.from_dict(item)
                self._validate_text(artifact.value, "value", self.max_value_chars)
                self._validate_text(artifact.origin_task_id, "origin_task_id", 256)
                if contains_sensitive_data(artifact.value) or contains_sensitive_data(
                    artifact.origin_task_id
                ):
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            artifacts.append(artifact)
        return artifacts

    @contextmanager
    def _exclusive_lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with lock_path.open("a+b") as lock_file:
            os.chmod(lock_path, 0o600)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _write(self) -> None:
        encoded = self._encode(self._artifacts)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            os.fchmod(file_descriptor, 0o600)
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                temporary_file.write(encoded)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, self.path)
            self._sync_directory()
        finally:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass

    def _sync_directory(self) -> None:
        try:
            directory_descriptor = os.open(self.path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory_descriptor)
        except OSError:
            pass
        finally:
            os.close(directory_descriptor)

    @staticmethod
    def _validate_text(value: str, name: str, max_chars: int) -> str:
        if not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
        clean_value = value.strip()
        if not clean_value:
            raise ValueError(f"{name} cannot be empty")
        if len(clean_value) > max_chars:
            raise ValueError(f"{name} exceeds {max_chars} characters")
        return clean_value

    @staticmethod
    def _encode(artifacts: list[ContextArtifact]) -> bytes:
        return json.dumps(
            [artifact.as_dict() for artifact in artifacts],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")


# Explicit aliases make the intent discoverable at integration sites without
# maintaining two implementations.
SessionContextStore = SessionContext
OperationalArtifact = ContextArtifact


__all__ = [
    "ArtifactKind",
    "ContextArtifact",
    "ContextResolution",
    "OperationalArtifact",
    "SessionContext",
    "SessionContextStore",
]
