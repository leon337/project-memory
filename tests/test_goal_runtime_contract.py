from context_anchor.goal_runtime import (
    EvidenceKind,
    EvidenceRecord,
    GoalContract,
    GoalCriterion,
    GoalRunState,
    GoalRunStatus,
    GoalVerifier,
)


def make_run() -> GoalRunState:
    return GoalRunState(
        contract=GoalContract(
            original_goal="Abra o editor e escreva Olá mundo",
            criteria=[
                GoalCriterion(id="editor_open", description="editor disponível"),
                GoalCriterion(id="text_present", description="texto Olá mundo presente"),
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
        )
    )

    verdict = GoalVerifier().evaluate(run)

    assert verdict.complete is False
    assert "editor_open" in verdict.pending_criteria
    assert run.status is GoalRunStatus.RUNNING


def test_observation_can_prove_criterion_but_other_required_criterion_keeps_goal_open():
    run = make_run()
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

    verdict = GoalVerifier().evaluate(run)

    assert verdict.complete is False
    assert verdict.pending_criteria == ("text_present",)


def test_all_required_criteria_need_independent_evidence_before_success():
    run = make_run()
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


def test_unverified_observation_never_proves_goal():
    run = make_run()
    run.record_evidence(
        EvidenceRecord(
            id="e1",
            criterion_id="editor_open",
            kind=EvidenceKind.OBSERVATION,
            source="active_window",
            verified=False,
        )
    )

    verdict = GoalVerifier().evaluate(run)

    assert verdict.complete is False
    assert "editor_open" in verdict.pending_criteria
