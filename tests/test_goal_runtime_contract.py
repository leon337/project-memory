from context_anchor.goal_runtime import (
    CriterionCheck,
    EvidenceKind,
    EvidenceRecord,
    GoalBudget,
    GoalContract,
    GoalCriterion,
    GoalRunState,
    GoalRunStatus,
    GoalStep,
    GoalStepStatus,
    GoalSubgoal,
    GoalVerifier,
    StepBlockReason,
)
import pytest


def make_run() -> GoalRunState:
    return GoalRunState(
        contract=GoalContract(
            original_goal="Abra o editor e escreva Olá mundo",
            criteria=[
                GoalCriterion(
                    id="editor_open",
                    description="editor disponível",
                    check=CriterionCheck.CONTAINS,
                    expected_value="xed",
                ),
                GoalCriterion(
                    id="text_present",
                    description="texto Olá mundo presente",
                    check=CriterionCheck.EQUALS,
                    expected_value="Olá mundo",
                ),
            ],
        )
    )


def test_execution_receipt_does_not_complete_criterion():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="editor_open",
            kind=EvidenceKind.EXECUTION_RECEIPT,
            source="open_app",
            verified=True,
            observed_value="xed",
        )
    )

    verdict = GoalVerifier().evaluate(run)

    assert verdict.complete is False
    assert "editor_open" in verdict.pending_criteria
    assert run.status is GoalRunStatus.RUNNING


def test_deserialized_string_receipt_cannot_bypass_evidence_kind_guard():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="receipt-from-json",
            criterion_id="editor_open",
            kind="execution_receipt",  # type: ignore[arg-type]
            source="deserialized",
            verified=True,
            observed_value="xed",
        )
    )

    assert GoalVerifier().evaluate(run).complete is False
    assert run.evidence[0].kind is EvidenceKind.EXECUTION_RECEIPT


def test_assertion_requires_explicit_criterion_opt_in():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="planner-assertion",
            criterion_id="editor_open",
            kind=EvidenceKind.ASSERTION,
            source="planner",
            verified=True,
            observed_value="xed",
        )
    )

    assert GoalVerifier().evaluate(run).complete is False


def test_observation_must_match_expected_value():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="editor_open",
            kind=EvidenceKind.OBSERVATION,
            source="active_window",
            verified=True,
            observed_value="Firefox",
        )
    )

    verdict = GoalVerifier().evaluate(run)

    assert verdict.complete is False
    assert "editor_open" in verdict.pending_criteria


def test_observation_can_prove_criterion_but_other_required_criterion_keeps_goal_open():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="editor_open",
            kind=EvidenceKind.OBSERVATION,
            source="active_window",
            verified=True,
            observed_value="xed — Documento não-salvo 1",
        )
    )

    verdict = GoalVerifier().evaluate(run)

    assert verdict.complete is False
    assert verdict.pending_criteria == ("text_present",)


def test_wrong_readback_does_not_complete_text_criterion():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="editor_open",
            kind=EvidenceKind.OBSERVATION,
            source="active_window",
            verified=True,
            observed_value="xed — Documento não-salvo 1",
        )
    )
    run.record_evidence(
        EvidenceRecord(
            id="e2",
            criterion_id="text_present",
            kind=EvidenceKind.READBACK,
            source="accessibility",
            verified=True,
            observed_value="Olá mund",
        )
    )

    verdict = GoalVerifier().evaluate(run)

    assert verdict.complete is False
    assert verdict.pending_criteria == ("text_present",)


def test_all_required_criteria_need_matching_independent_evidence_before_success():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="editor_open",
            kind=EvidenceKind.OBSERVATION,
            source="active_window",
            verified=True,
            observed_value="xed — Documento não-salvo 1",
        )
    )
    run.record_evidence(
        EvidenceRecord(
            id="e2",
            criterion_id="text_present",
            kind=EvidenceKind.READBACK,
            source="accessibility",
            verified=True,
            observed_value="Olá mundo",
        )
    )

    verdict = GoalVerifier().finalize(run)

    assert verdict.complete is True
    assert verdict.status is GoalRunStatus.SUCCEEDED
    assert run.status is GoalRunStatus.SUCCEEDED


def test_contract_rejects_cyclic_or_duplicated_subgoal_ownership() -> None:
    with pytest.raises(ValueError, match="DAG"):
        GoalContract(
            original_goal="objetivo",
            criteria=[
                GoalCriterion(id="c1", description="efeito 1"),
                GoalCriterion(id="c2", description="efeito 2"),
            ],
            subgoals=[
                GoalSubgoal("a", "a", depends_on=["b"], produces=["c1"]),
                GoalSubgoal("b", "b", depends_on=["a"], produces=["c2"]),
            ],
        )

    with pytest.raises(ValueError, match="multiple subgoals"):
        GoalContract(
            original_goal="objetivo",
            criteria=[GoalCriterion(id="c", description="efeito")],
            subgoals=[
                GoalSubgoal("a", "a", produces=["c"]),
                GoalSubgoal("b", "b", produces=["c"]),
            ],
        )


def test_verifier_requires_every_subgoal_not_only_matching_criteria() -> None:
    run = GoalRunState(
        contract=GoalContract(
            original_goal="observar em ordem",
            criteria=[
                GoalCriterion(
                    id="first",
                    description="primeiro efeito",
                    check=CriterionCheck.TRUTHY,
                ),
                GoalCriterion(
                    id="second",
                    description="segundo efeito",
                    check=CriterionCheck.TRUTHY,
                ),
            ],
            subgoals=[
                GoalSubgoal("one", "primeiro", produces=["first"]),
                GoalSubgoal(
                    "two",
                    "segundo",
                    depends_on=["one"],
                    produces=["second"],
                ),
            ],
        )
    )
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="first",
            kind=EvidenceKind.OBSERVATION,
            source="observer",
            verified=True,
            observed_value=True,
        )
    )

    verdict = GoalVerifier().finalize(run)

    assert verdict.complete is False
    assert run.contract.subgoals[0].status.value == "satisfied"
    assert run.contract.subgoals[1].status.value == "running"


def test_unverified_observation_never_proves_goal():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="editor_open",
            kind=EvidenceKind.OBSERVATION,
            source="active_window",
            verified=False,
            observed_value="xed",
        )
    )

    verdict = GoalVerifier().evaluate(run)

    assert verdict.complete is False
    assert "editor_open" in verdict.pending_criteria


def test_truthy_check_requires_truthy_observation():
    run = GoalRunState(
        contract=GoalContract(
            original_goal="Verifique se há resultado",
            criteria=[
                GoalCriterion(
                    id="result_exists",
                    description="resultado existe",
                    check=CriterionCheck.TRUTHY,
                )
            ],
        )
    )
    verifier = GoalVerifier()

    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="result_exists",
            kind=EvidenceKind.OBSERVATION,
            source="browser",
            verified=True,
            observed_value="",
        )
    )
    assert verifier.evaluate(run).complete is False

    run.record_evidence(
        EvidenceRecord(
            id="e2",
            criterion_id="result_exists",
            kind=EvidenceKind.OBSERVATION,
            source="browser",
            verified=True,
            observed_value="Primeiro resultado",
        )
    )
    assert verifier.finalize(run).complete is True


def test_successful_step_is_not_goal_evidence():
    run = make_run()
    run.record_step(
        GoalStep(
            id="s1",
            action_key="open_editor",
            strategy="desktop",
            status=GoalStepStatus.SUCCEEDED,
            provider="xdotool",
            made_progress=True,
        )
    )

    verdict = GoalVerifier().finalize(run)

    assert verdict.complete is False
    assert run.status is GoalRunStatus.RUNNING
    assert verdict.pending_criteria == ("editor_open", "text_present")


def test_step_budget_is_enforced():
    run = GoalRunState(contract=make_run().contract, budget=GoalBudget(max_steps=1))
    run.record_step(
        GoalStep("s1", "open_editor", "desktop", GoalStepStatus.FAILED)
    )

    guard = run.can_attempt_step("observe_editor", "accessibility")

    assert guard.allowed is False
    assert guard.reason is StepBlockReason.STEP_BUDGET_EXHAUSTED


def test_retry_budget_is_scoped_per_action_and_strategy():
    run = GoalRunState(
        contract=make_run().contract,
        budget=GoalBudget(
            max_retries_per_strategy=1,
            max_repeated_actions=10,
            max_no_progress_steps=10,
        ),
    )
    for number in (1, 2):
        run.record_step(
            GoalStep(
                f"s{number}",
                "open_editor",
                "desktop",
                GoalStepStatus.FAILED,
            )
        )

    exhausted = run.can_attempt_step("open_editor", "desktop")
    fallback = run.can_attempt_step("open_editor", "shell")

    assert exhausted.reason is StepBlockReason.RETRY_BUDGET_EXHAUSTED
    assert fallback.allowed is True


def test_fallback_cannot_repeat_an_action_that_already_succeeded():
    run = make_run()
    run.record_step(
        GoalStep(
            "s1",
            "open_editor",
            "desktop",
            GoalStepStatus.SUCCEEDED,
            provider="xdotool",
        )
    )

    guard = run.can_attempt_step("open_editor", "shell")

    assert guard.allowed is False
    assert guard.reason is StepBlockReason.ACTION_ALREADY_COMPLETED


def test_repetition_and_no_progress_are_detected_and_replan_resets_stall():
    repeated_run = GoalRunState(
        contract=make_run().contract,
        budget=GoalBudget(
            max_retries_per_strategy=10,
            max_repeated_actions=2,
            max_no_progress_steps=10,
        ),
    )
    for number in (1, 2):
        repeated_run.record_step(
            GoalStep(
                f"r{number}",
                "search",
                "browser",
                GoalStepStatus.FAILED,
            )
        )
    assert (
        repeated_run.can_attempt_step("search", "browser").reason
        is StepBlockReason.REPETITION_DETECTED
    )

    stalled_run = GoalRunState(
        contract=make_run().contract,
        budget=GoalBudget(max_no_progress_steps=2),
    )
    stalled_run.record_step(
        GoalStep("n1", "open", "desktop", GoalStepStatus.FAILED)
    )
    stalled_run.record_step(
        GoalStep("n2", "observe", "accessibility", GoalStepStatus.FAILED)
    )
    assert (
        stalled_run.can_attempt_step("replan", "planner").reason
        is StepBlockReason.NO_PROGRESS_DETECTED
    )

    stalled_run.acknowledge_replan()

    assert stalled_run.can_attempt_step("replan", "planner").allowed is True
    assert stalled_run.replan_count == 1


def test_metrics_report_ids_progress_providers_fallbacks_and_retries():
    run = GoalRunState(
        contract=make_run().contract,
        goal_id="goal-1",
        task_id="task-1",
        budget=GoalBudget(max_no_progress_steps=10),
    )
    run.record_step(
        GoalStep(
            "s1",
            "open_editor",
            "desktop",
            GoalStepStatus.FAILED,
            provider="xdotool",
        )
    )
    run.record_step(
        GoalStep(
            "s2",
            "open_editor",
            "desktop",
            GoalStepStatus.FAILED,
            provider="xdotool",
        )
    )
    run.record_step(
        GoalStep(
            "s3",
            "open_editor",
            "shell",
            GoalStepStatus.SUCCEEDED,
            provider="subprocess",
            fallback_from="desktop",
            made_progress=True,
        )
    )
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="editor_open",
            kind=EvidenceKind.OBSERVATION,
            source="active_window",
            verified=True,
            observed_value="xed",
        )
    )
    GoalVerifier().finalize(run)

    metrics = run.metrics()
    serialized = metrics.as_dict()

    assert serialized["goal_id"] == "goal-1"
    assert serialized["task_id"] == "task-1"
    assert serialized["steps"] == 3
    assert serialized["criteria"] == {"satisfied": 1, "pending": 1}
    assert serialized["providers"] == ["subprocess", "xdotool"]
    assert serialized["fallbacks"] == 1
    assert serialized["retries"] == {"total": 1, "by_strategy": {"desktop": 1}}
    assert serialized["strategies"] == ["desktop", "shell"]


def test_duplicate_evidence_and_step_ids_are_rejected():
    run = make_run()
    evidence = EvidenceRecord(
        id="e1",
        criterion_id="editor_open",
        kind=EvidenceKind.OBSERVATION,
        source="active_window",
        verified=True,
        observed_value="xed",
    )
    run.record_evidence(evidence)
    try:
        run.record_evidence(evidence)
    except ValueError as error:
        assert "Duplicate evidence id" in str(error)
    else:
        raise AssertionError("duplicate evidence id was accepted")

    step = GoalStep("s1", "open", "desktop", GoalStepStatus.FAILED)
    run.record_step(step)
    try:
        run.record_step(step)
    except ValueError as error:
        assert "Duplicate step id" in str(error)
    else:
        raise AssertionError("duplicate step id was accepted")


def test_contract_rejects_duplicate_criterion_ids():
    with pytest.raises(ValueError, match="criteria ids must be unique"):
        GoalContract(
            original_goal="duplicado",
            criteria=[
                GoalCriterion("same", "primeiro"),
                GoalCriterion("same", "segundo"),
            ],
        )


def test_evidence_with_step_id_is_linked_and_unknown_step_is_rejected():
    run = make_run()
    run.record_step(
        GoalStep("known-step", "open", "desktop", GoalStepStatus.SUCCEEDED)
    )
    evidence = EvidenceRecord(
        id="linked-evidence",
        criterion_id="editor_open",
        kind=EvidenceKind.OBSERVATION,
        source="active_window",
        verified=True,
        observed_value="xed",
        step_id="known-step",
    )
    run.record_evidence(evidence)

    assert run.steps[0].evidence_ids == ["linked-evidence"]

    with pytest.raises(ValueError, match="Unknown evidence step id"):
        run.record_evidence(
            EvidenceRecord(
                id="orphan",
                criterion_id="editor_open",
                kind=EvidenceKind.OBSERVATION,
                source="active_window",
                verified=True,
                observed_value="xed",
                step_id="missing",
            )
        )


def test_verifier_rejects_a_contract_without_required_criteria():
    run = GoalRunState(GoalContract(original_goal="objetivo vazio", criteria=[]))

    verdict = GoalVerifier().finalize(run)

    assert verdict.complete is False
    assert verdict.status is GoalRunStatus.FAILED
    assert "no required completion criteria" in verdict.reason
    assert run.status is GoalRunStatus.FAILED
