from context_anchor.goal_interpreter import IntentKind, SemanticGoalInterpreter
from context_anchor.policy import Plan


def test_exact_modifier_is_instruction_not_written_payload() -> None:
    command = "Abra um editor de texto e escreva exatamente: Validação real número 1"

    intent = SemanticGoalInterpreter().interpret(command)

    assert intent.kind is IntentKind.OPEN_AND_WRITE
    assert intent.text == "Validação real número 1"
    assert intent.plans == (
        Plan("open_app", "editor"),
        Plan("type_text", "Validação real número 1"),
    )
