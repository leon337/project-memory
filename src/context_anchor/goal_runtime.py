from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


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


class GoalStepStatus(str, Enum):
    """Operational outcome of one attempted step.

    ``SUCCEEDED`` means only that the operation was executed successfully.  It
    does not prove any goal criterion; that remains the verifier's job.
    """

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StepBlockReason(str, Enum):
    STEP_BUDGET_EXHAUSTED = "step_budget_exhausted"
    RETRY_BUDGET_EXHAUSTED = "retry_budget_exhausted"
    ACTION_ALREADY_COMPLETED = "action_already_completed"
    REPETITION_DETECTED = "repetition_detected"
    NO_PROGRESS_DETECTED = "no_progress_detected"


class EvidenceKind(str, Enum):
    EXECUTION_RECEIPT = "execution_receipt"
    OBSERVATION = "observation"
    READBACK = "readback"
    ASSERTION = "assertion"


class CriterionCheck(str, Enum):
    """Small deterministic checks used by the first Goal Verifier increment."""

    ANY_VERIFIED_EVIDENCE = "any_verified_evidence"
    EQUALS = "equals"
    CONTAINS = "contains"
    TRUTHY = "truthy"


@dataclass(frozen=True, slots=True)
class GoalBudget:
    """Finite, generic limits for an autonomous goal run.

    Retry limits are counted *after* the first attempt and are scoped to the
    pair ``(action_key, strategy)``.  A fallback therefore has its own retry
    allowance, while a successfully executed action is never blindly repeated
    by another fallback.
    """

    max_steps: int = 32
    max_retries_per_strategy: int = 2
    max_repeated_actions: int = 3
    max_no_progress_steps: int = 3

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be greater than zero")
        if self.max_retries_per_strategy < 0:
            raise ValueError("max_retries_per_strategy cannot be negative")
        if self.max_repeated_actions <= 0:
            raise ValueError("max_repeated_actions must be greater than zero")
        if self.max_no_progress_steps <= 0:
            raise ValueError("max_no_progress_steps must be greater than zero")


@dataclass(slots=True)
class GoalStep:
    """A completed operational attempt made while pursuing a goal."""

    id: str
    action_key: str
    strategy: str
    status: GoalStepStatus
    provider: str | None = None
    subgoal_id: str | None = None
    fallback_from: str | None = None
    made_progress: bool = False
    evidence_ids: list[str] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True, slots=True)
class StepGuard:
    allowed: bool
    reason: StepBlockReason | None = None
    detail: str = ""

    def __bool__(self) -> bool:
        return self.allowed


@dataclass(frozen=True, slots=True)
class GoalRunMetrics:
    """Serializable run summary for logs, SQLite and operator surfaces."""

    goal_id: str
    task_id: str
    status: GoalRunStatus
    steps: int
    satisfied_subgoals: int
    pending_subgoals: int
    satisfied_criteria: int
    pending_criteria: int
    providers: tuple[str, ...]
    fallbacks: int
    retries: int
    strategies: tuple[str, ...]
    retries_by_strategy: tuple[tuple[str, int], ...]
    final_reason: str | None
    last_block_reason: StepBlockReason | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "steps": self.steps,
            "subgoals": {
                "satisfied": self.satisfied_subgoals,
                "pending": self.pending_subgoals,
            },
            "criteria": {
                "satisfied": self.satisfied_criteria,
                "pending": self.pending_criteria,
            },
            "providers": list(self.providers),
            "fallbacks": self.fallbacks,
            "retries": {
                "total": self.retries,
                "by_strategy": dict(self.retries_by_strategy),
            },
            "strategies": list(self.strategies),
            "final_reason": self.final_reason,
            "last_block_reason": (
                self.last_block_reason.value if self.last_block_reason is not None else None
            ),
        }


@dataclass(slots=True)
class GoalCriterion:
    id: str
    description: str
    required: bool = True
    check: CriterionCheck = CriterionCheck.ANY_VERIFIED_EVIDENCE
    expected_value: Any = None
    status: ProgressStatus = ProgressStatus.PENDING
    evidence_ids: list[str] = field(default_factory=list)
    allowed_evidence_kinds: tuple[EvidenceKind, ...] = (
        EvidenceKind.OBSERVATION,
        EvidenceKind.READBACK,
    )

    def __post_init__(self) -> None:
        self.check = CriterionCheck(self.check)
        self.status = ProgressStatus(self.status)
        self.allowed_evidence_kinds = tuple(
            EvidenceKind(kind) for kind in self.allowed_evidence_kinds
        )


@dataclass(slots=True)
class GoalSubgoal:
    id: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    status: ProgressStatus = ProgressStatus.PENDING
    produces: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.status = ProgressStatus(self.status)


@dataclass(slots=True)
class EvidenceRecord:
    id: str
    criterion_id: str
    kind: EvidenceKind
    source: str
    verified: bool
    observed_value: Any = None
    step_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.kind = EvidenceKind(self.kind)

    @property
    def proves_effect(self) -> bool:
        """Execution receipts are never sufficient proof of a goal effect by themselves."""
        return self.verified and EvidenceKind(self.kind) is not EvidenceKind.EXECUTION_RECEIPT


@dataclass(slots=True)
class GoalContract:
    original_goal: str
    criteria: list[GoalCriterion]
    subgoals: list[GoalSubgoal] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        criterion_ids = [item.id for item in self.criteria]
        subgoal_ids = [item.id for item in self.subgoals]
        if len(criterion_ids) != len(set(criterion_ids)):
            raise ValueError("Goal criteria ids must be unique")
        if len(subgoal_ids) != len(set(subgoal_ids)):
            raise ValueError("Goal subgoal ids must be unique")
        known_subgoals = set(subgoal_ids)
        known_criteria = set(criterion_ids)
        criterion_owners: dict[str, str] = {}
        for subgoal in self.subgoals:
            if len(subgoal.depends_on) != len(set(subgoal.depends_on)):
                raise ValueError(f"Duplicate dependencies for subgoal {subgoal.id}")
            if subgoal.id in subgoal.depends_on:
                raise ValueError(f"Subgoal {subgoal.id} cannot depend on itself")
            unknown = set(subgoal.depends_on) - known_subgoals
            if unknown:
                raise ValueError(
                    f"Unknown subgoal dependencies for {subgoal.id}: {sorted(unknown)}"
                )
            if not subgoal.produces:
                raise ValueError(f"Subgoal {subgoal.id} must own completion criteria")
            if len(subgoal.produces) != len(set(subgoal.produces)):
                raise ValueError(f"Duplicate criteria owned by subgoal {subgoal.id}")
            unknown_criteria = set(subgoal.produces) - known_criteria
            if unknown_criteria:
                raise ValueError(
                    f"Unknown criteria produced by {subgoal.id}: "
                    f"{sorted(unknown_criteria)}"
                )
            for criterion_id in subgoal.produces:
                if criterion_id in criterion_owners:
                    raise ValueError(
                        f"Criterion {criterion_id} is owned by multiple subgoals"
                    )
                criterion_owners[criterion_id] = subgoal.id

        if self.subgoals and set(criterion_ids) != set(criterion_owners):
            missing = sorted(set(criterion_ids) - set(criterion_owners))
            raise ValueError(f"Goal criterion has no subgoal owner: {missing[0]}")

        dependencies = {item.id: tuple(item.depends_on) for item in self.subgoals}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(subgoal_id: str) -> None:
            if subgoal_id in visiting:
                raise ValueError("Goal subgoal dependencies must form a DAG")
            if subgoal_id in visited:
                return
            visiting.add(subgoal_id)
            for dependency_id in dependencies[subgoal_id]:
                visit(dependency_id)
            visiting.remove(subgoal_id)
            visited.add(subgoal_id)

        for subgoal_id in subgoal_ids:
            visit(subgoal_id)

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
    budget: GoalBudget = field(default_factory=GoalBudget)
    steps: list[GoalStep] = field(default_factory=list)
    goal_id: str = field(default_factory=lambda: uuid4().hex)
    task_id: str = field(default_factory=lambda: uuid4().hex)
    consecutive_no_progress: int = 0
    replan_count: int = 0
    final_reason: str | None = None
    last_block_reason: StepBlockReason | None = None

    def record_evidence(self, item: EvidenceRecord) -> None:
        criterion = self.contract.criterion(item.criterion_id)
        if any(existing.id == item.id for existing in self.evidence):
            raise ValueError(f"Duplicate evidence id: {item.id}")
        step: GoalStep | None = None
        if item.step_id is not None:
            step = next(
                (candidate for candidate in self.steps if candidate.id == item.step_id),
                None,
            )
            if step is None:
                raise ValueError(f"Unknown evidence step id: {item.step_id}")
        self.evidence.append(item)
        criterion.evidence_ids.append(item.id)
        if step is not None and item.id not in step.evidence_ids:
            step.evidence_ids.append(item.id)

    def evidence_for(self, criterion_id: str) -> list[EvidenceRecord]:
        return [item for item in self.evidence if item.criterion_id == criterion_id]

    def attempts_for(self, action_key: str, strategy: str) -> int:
        return sum(
            1
            for step in self.steps
            if step.action_key == action_key and step.strategy == strategy
        )

    def retries_for(self, action_key: str, strategy: str) -> int:
        return max(0, self.attempts_for(action_key, strategy) - 1)

    def action_was_completed(self, action_key: str) -> bool:
        return any(
            step.action_key == action_key and step.status is GoalStepStatus.SUCCEEDED
            for step in self.steps
        )

    def _consecutive_repetitions(self, action_key: str, strategy: str) -> int:
        count = 0
        for step in reversed(self.steps):
            if step.action_key != action_key or step.strategy != strategy:
                break
            count += 1
        return count

    def can_attempt_step(self, action_key: str, strategy: str) -> StepGuard:
        """Return a deterministic guard decision without executing anything."""

        if self.action_was_completed(action_key):
            return self._blocked(
                StepBlockReason.ACTION_ALREADY_COMPLETED,
                f"action {action_key!r} already completed successfully",
            )

        if self.step_count >= self.budget.max_steps:
            return self._blocked(
                StepBlockReason.STEP_BUDGET_EXHAUSTED,
                f"step budget exhausted ({self.budget.max_steps})",
            )

        attempts = self.attempts_for(action_key, strategy)
        if attempts >= self.budget.max_retries_per_strategy + 1:
            return self._blocked(
                StepBlockReason.RETRY_BUDGET_EXHAUSTED,
                f"retry budget exhausted for strategy {strategy!r}",
            )

        if (
            self._consecutive_repetitions(action_key, strategy)
            >= self.budget.max_repeated_actions
        ):
            return self._blocked(
                StepBlockReason.REPETITION_DETECTED,
                f"repetition limit reached for action {action_key!r}",
            )

        if self.consecutive_no_progress >= self.budget.max_no_progress_steps:
            return self._blocked(
                StepBlockReason.NO_PROGRESS_DETECTED,
                "no-progress threshold reached; replan before another attempt",
            )

        self.last_block_reason = None
        return StepGuard(allowed=True)

    def _blocked(self, reason: StepBlockReason, detail: str) -> StepGuard:
        self.last_block_reason = reason
        return StepGuard(allowed=False, reason=reason, detail=detail)

    def record_step(self, step: GoalStep) -> None:
        """Record one attempted operation, enforcing all run guards.

        The method deliberately does not update goal criteria.  Callers must
        record independent evidence and let :class:`GoalVerifier` decide goal
        completion.
        """

        if any(existing.id == step.id for existing in self.steps):
            raise ValueError(f"Duplicate step id: {step.id}")

        guard = self.can_attempt_step(step.action_key, step.strategy)
        if not guard:
            raise RuntimeError(guard.detail)

        self.steps.append(step)
        self.step_count += 1
        if step.made_progress:
            self.consecutive_no_progress = 0
        else:
            self.consecutive_no_progress += 1

    def acknowledge_replan(self) -> None:
        """Start a new plan epoch after a detected stall."""

        self.replan_count += 1
        self.consecutive_no_progress = 0
        self.last_block_reason = None

    def metrics(self) -> GoalRunMetrics:
        retry_counts: dict[str, int] = {}
        attempts: dict[tuple[str, str], int] = {}
        for step in self.steps:
            key = (step.action_key, step.strategy)
            attempts[key] = attempts.get(key, 0) + 1
        for (_, strategy), count in attempts.items():
            retries = max(0, count - 1)
            if retries:
                retry_counts[strategy] = retry_counts.get(strategy, 0) + retries

        satisfied_criteria = sum(
            criterion.status is ProgressStatus.SATISFIED
            for criterion in self.contract.criteria
        )
        satisfied_subgoals = sum(
            subgoal.status is ProgressStatus.SATISFIED
            for subgoal in self.contract.subgoals
        )
        providers = tuple(sorted({step.provider for step in self.steps if step.provider}))
        strategies = tuple(sorted({step.strategy for step in self.steps}))

        return GoalRunMetrics(
            goal_id=self.goal_id,
            task_id=self.task_id,
            status=self.status,
            steps=self.step_count,
            satisfied_subgoals=satisfied_subgoals,
            pending_subgoals=len(self.contract.subgoals) - satisfied_subgoals,
            satisfied_criteria=satisfied_criteria,
            pending_criteria=len(self.contract.criteria) - satisfied_criteria,
            providers=providers,
            fallbacks=sum(step.fallback_from is not None for step in self.steps),
            retries=sum(retry_counts.values()),
            strategies=strategies,
            retries_by_strategy=tuple(sorted(retry_counts.items())),
            final_reason=self.final_reason or self.failure_reason,
            last_block_reason=self.last_block_reason,
        )


@dataclass(frozen=True, slots=True)
class GoalVerdict:
    complete: bool
    status: GoalRunStatus
    reason: str
    pending_criteria: tuple[str, ...] = ()


class GoalVerifier:
    """Deterministic authority for goal completion semantics.

    Planner intent, successful execution and `verified=True` receipts are not
    enough by themselves. A criterion is satisfied only by independent evidence
    whose observed value also passes the criterion's deterministic check.
    """

    @staticmethod
    def _matches(criterion: GoalCriterion, item: EvidenceRecord) -> bool:
        if not item.proves_effect:
            return False
        if EvidenceKind(item.kind) not in criterion.allowed_evidence_kinds:
            return False

        if criterion.check is CriterionCheck.ANY_VERIFIED_EVIDENCE:
            return True

        if criterion.check is CriterionCheck.TRUTHY:
            return bool(item.observed_value)

        if criterion.check is CriterionCheck.EQUALS:
            return item.observed_value == criterion.expected_value

        if criterion.check is CriterionCheck.CONTAINS:
            expected = criterion.expected_value
            observed = item.observed_value
            if expected is None or observed is None:
                return False
            if isinstance(observed, str):
                return str(expected) in observed
            try:
                return expected in observed
            except TypeError:
                return False

        return False

    def _criterion_is_satisfied(self, run: GoalRunState, criterion: GoalCriterion) -> bool:
        return any(self._matches(criterion, item) for item in run.evidence_for(criterion.id))

    @staticmethod
    def _refresh_subgoals(run: GoalRunState) -> tuple[str, ...]:
        if not run.contract.subgoals:
            return ()
        by_id = {item.id: item for item in run.contract.subgoals}
        criteria = {item.id: item for item in run.contract.criteria}
        refreshed: set[str] = set()

        def refresh(subgoal: GoalSubgoal) -> None:
            if subgoal.id in refreshed:
                return
            for dependency_id in subgoal.depends_on:
                refresh(by_id[dependency_id])
            dependency_statuses = [
                by_id[dependency_id].status for dependency_id in subgoal.depends_on
            ]
            effects = [criteria[criterion_id] for criterion_id in subgoal.produces]
            if any(
                status in {ProgressStatus.BLOCKED, ProgressStatus.FAILED}
                for status in dependency_statuses
            ):
                subgoal.status = ProgressStatus.BLOCKED
            elif all(
                status is ProgressStatus.SATISFIED for status in dependency_statuses
            ) and all(effect.status is ProgressStatus.SATISFIED for effect in effects):
                subgoal.status = ProgressStatus.SATISFIED
            elif all(
                status is ProgressStatus.SATISFIED for status in dependency_statuses
            ):
                subgoal.status = ProgressStatus.RUNNING
            else:
                subgoal.status = ProgressStatus.PENDING
            refreshed.add(subgoal.id)

        for item in run.contract.subgoals:
            refresh(item)
        return tuple(
            item.id
            for item in run.contract.subgoals
            if item.status is not ProgressStatus.SATISFIED
        )

    def evaluate(self, run: GoalRunState) -> GoalVerdict:
        if run.failure_reason:
            return GoalVerdict(
                complete=False,
                status=GoalRunStatus.FAILED,
                reason=run.failure_reason,
            )

        if not any(criterion.required for criterion in run.contract.criteria):
            return GoalVerdict(
                complete=False,
                status=GoalRunStatus.FAILED,
                reason="goal contract has no required completion criteria",
            )

        pending: list[str] = []
        for criterion in run.contract.criteria:
            if self._criterion_is_satisfied(run, criterion):
                criterion.status = ProgressStatus.SATISFIED
            else:
                criterion.status = ProgressStatus.PENDING
                if criterion.required:
                    pending.append(criterion.id)

        pending_subgoals = self._refresh_subgoals(run)

        if pending:
            return GoalVerdict(
                complete=False,
                status=GoalRunStatus.RUNNING,
                reason="required goal criteria are still unproven",
                pending_criteria=tuple(pending),
            )

        if pending_subgoals:
            return GoalVerdict(
                complete=False,
                status=GoalRunStatus.RUNNING,
                reason="required goal subgoals are still incomplete: "
                + ", ".join(pending_subgoals),
            )

        return GoalVerdict(
            complete=True,
            status=GoalRunStatus.SUCCEEDED,
            reason="all required goal criteria are proven by matching evidence",
        )

    def finalize(self, run: GoalRunState) -> GoalVerdict:
        verdict = self.evaluate(run)
        if verdict.complete:
            run.status = GoalRunStatus.SUCCEEDED
            run.final_reason = verdict.reason
        elif verdict.status is GoalRunStatus.FAILED:
            run.status = GoalRunStatus.FAILED
            run.final_reason = verdict.reason
        else:
            run.status = GoalRunStatus.RUNNING
            run.final_reason = None
        return verdict
