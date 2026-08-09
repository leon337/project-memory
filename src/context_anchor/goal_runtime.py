from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ProgressStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SATISFIED = "satisfied"
    BLOCKED = "blocked"
    FAILED = "failed"


class GoalRunStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EvidenceKind(str, Enum):
    EXECUTION_RECEIPT = "execution_receipt"
    OBSERVATION = "observation"
    READBACK = "readback"
    ASSERTION = "assertion"


@dataclass(slots=True)
class GoalCriterion:
    id: str
    description: str
    required: bool = True
    status: ProgressStatus = ProgressStatus.PENDING
    evidence_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GoalSubgoal:
    id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    status: ProgressStatus = ProgressStatus.PENDING
    produces: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EvidenceRecord:
    id: str
    criterion_id: str
    kind: EvidenceKind
    source: str
    verified: bool
    observed_value: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def proves_effect(self) -> bool:
        """Execution receipts are never sufficient proof of a goal effect by themselves."""
        return self.verified and self.kind is not EvidenceKind.EXECUTION_RECEIPT


@dataclass(slots=True)
class GoalContract:
    original_goal: str
    criteria: list[GoalCriterion]
    subgoals: list[GoalSubgoal] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def criterion(self, criterion_id: str) -> GoalCriterion:
        for item in self.criteria:
            if item.id == criterion_id:
                return item
        raise KeyError(f"Unknown goal criterion: {criterion_id}")


@dataclass(slots=True)
class GoalRunState:
    contract: GoalContract
    evidence: list[EvidenceRecord] = field(default_factory=list)
    status: GoalRunStatus = GoalRunStatus.RUNNING
    step_count: int = 0
    failure_reason: str | None = None

    def record_evidence(self, item: EvidenceRecord) -> None:
        criterion = self.contract.criterion(item.criterion_id)
        self.evidence.append(item)
        criterion.evidence_ids.append(item.id)
        if item.proves_effect:
            criterion.status = ProgressStatus.SATISFIED

    def evidence_for(self, criterion_id: str) -> list[EvidenceRecord]:
        return [item for item in self.evidence if item.criterion_id == criterion_id]


@dataclass(frozen=True, slots=True)
class GoalVerdict:
    complete: bool
    status: GoalRunStatus
    reason: str
    pending_criteria: tuple[str, ...] = ()


class GoalVerifier:
    """Deterministic authority for the first increment of goal completion semantics."""

    def evaluate(self, run: GoalRunState) -> GoalVerdict:
        if run.failure_reason:
            return GoalVerdict(
                complete=False,
                status=GoalRunStatus.FAILED,
                reason=run.failure_reason,
            )

        pending: list[str] = []
        for criterion in run.contract.criteria:
            if not criterion.required:
                continue

            proof = any(item.proves_effect for item in run.evidence_for(criterion.id))
            if criterion.status is not ProgressStatus.SATISFIED or not proof:
                pending.append(criterion.id)

        if pending:
            return GoalVerdict(
                complete=False,
                status=GoalRunStatus.RUNNING,
                reason="required goal criteria are still unproven",
                pending_criteria=tuple(pending),
            )

        return GoalVerdict(
            complete=True,
            status=GoalRunStatus.SUCCEEDED,
            reason="all required goal criteria are proven by evidence",
        )

    def finalize(self, run: GoalRunState) -> GoalVerdict:
        verdict = self.evaluate(run)
        if verdict.complete:
            run.status = GoalRunStatus.SUCCEEDED
        elif verdict.status is GoalRunStatus.FAILED:
            run.status = GoalRunStatus.FAILED
        else:
            run.status = GoalRunStatus.RUNNING
        return verdict
