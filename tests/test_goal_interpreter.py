import pytest

from context_anchor.goal_interpreter import (
    GoalIntentKind,
    IntentKind,
    SemanticGoalInterpreter,
)
from context_anchor.policy import Plan


@pytest.fixture
def interpreter() -> SemanticGoalInterpreter:
    return SemanticGoalInterpreter()


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("Abra o editor de texto e escreva Olá mundo", "Olá mundo"),
        ("Inicie o bloco de notas; depois digite \"Ata da reunião\".", "Ata da reunião"),
        ("Lance um editor e insira o texto: lembrete importante", "lembrete importante"),
    ],
)
def test_open_and_write_is_recognized_by_concepts_and_preserves_text(
    interpreter: SemanticGoalInterpreter, command: str, expected: str
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.OPEN_AND_WRITE
    assert intent.capability == "text.edit"
    assert intent.text == expected


def test_existing_unambiguous_open_and_write_keeps_policy_plans(
    interpreter: SemanticGoalInterpreter,
) -> None:
    intent = interpreter.interpret("Abra o editor de texto e escreva Olá mundo")

    assert intent.plans == (
        Plan("open_app", "editor"),
        Plan("type_text", "Olá mundo"),
    )


@pytest.mark.parametrize(
    ("command", "expected_url"),
    [
        ("abra example.com", "https://example.com"),
        ("Visite https://example.org/docs", "https://example.org/docs"),
        ("Quero ir para localhost:8080/status", "https://localhost:8080/status"),
    ],
)
def test_url_navigation_is_a_typed_deterministic_intent(
    interpreter: SemanticGoalInterpreter, command: str, expected_url: str
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.DETERMINISTIC
    assert intent.capability == "browser.navigate"
    assert intent.url == expected_url
    assert intent.plans


@pytest.mark.parametrize(
    ("command", "browser", "url", "query"),
    [
        (
            "Abra o navegador brave e acesse o site google.com e pesquise São Lourenço da Mata",
            "brave-browser",
            "https://google.com",
            "São Lourenço da Mata",
        ),
        (
            "Inicie o Firefox, visite bing.com e busque por energia solar",
            "firefox",
            "https://bing.com",
            "energia solar",
        ),
        (
            "No Chromium, acesse duckduckgo.com e procure sobre testes de software",
            "chromium",
            "https://duckduckgo.com",
            "testes de software",
        ),
    ],
)
def test_named_browser_site_search_extracts_independent_entities(
    interpreter: SemanticGoalInterpreter,
    command: str,
    browser: str,
    url: str,
    query: str,
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.NAMED_BROWSER_SEARCH
    assert intent.browser == browser
    assert intent.url == url
    assert intent.query == query
    assert intent.capabilities == ("browser.navigate", "web.search")


@pytest.mark.parametrize(
    ("command", "query"),
    [
        ("Pesquise inteligência artificial", "inteligência artificial"),
        ("Busque por agricultura regenerativa", "agricultura regenerativa"),
        ("Procure na internet sobre computação quântica, por favor", "computação quântica"),
    ],
)
def test_simple_search_variants_do_not_require_a_provider(
    interpreter: SemanticGoalInterpreter, command: str, query: str
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.SEARCH
    assert intent.capability == "web.search"
    assert intent.query == query


@pytest.mark.parametrize(
    ("command", "query"),
    [
        ("Quero saber o significado do nome Josiel.", "significado do nome Josiel"),
        ("Você pode explicar o que significa resiliência?", "o que significa resiliência?"),
        ("Gostaria de saber quem é Ada Lovelace.", "quem é Ada Lovelace"),
    ],
)
def test_information_needs_become_search_and_read_intents(
    interpreter: SemanticGoalInterpreter, command: str, query: str
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.INFORMATION
    assert intent.query == query
    assert intent.capabilities == ("web.search", "web.read")


@pytest.mark.parametrize("alias", ["VS Code", "Visual Studio Code", "vscode"])
def test_code_editor_aliases_converge_on_code_edit_capability(
    interpreter: SemanticGoalInterpreter, alias: str
) -> None:
    intent = interpreter.interpret(f"Abra o {alias}")

    assert intent.kind is IntentKind.OPEN_CAPABILITY
    assert intent.capability == "code.edit"
    assert intent.app_hint is not None


@pytest.mark.parametrize(
    "command",
    [
        "Preciso fazer algumas contas.",
        "Quero calcular uns valores.",
        "Abra uma calculadora para mim, por favor.",
    ],
)
def test_calculation_need_resolves_to_a_capability_not_an_executable(
    interpreter: SemanticGoalInterpreter, command: str
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.OPEN_CAPABILITY
    assert intent.capability == "calculate"


@pytest.mark.parametrize(
    "command",
    [
        "Quero fazer uma anotação. Abra alguma coisa onde eu possa escrever.",
        "Preciso anotar uma ideia; inicie uma ferramenta de texto.",
        "Gostaria de tomar notas.",
    ],
)
def test_note_need_resolves_to_text_edit_capability(
    interpreter: SemanticGoalInterpreter, command: str
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.OPEN_CAPABILITY
    assert intent.capability == "text.edit"
    assert intent.text is None


@pytest.mark.parametrize(
    ("command", "query"),
    [
        (
            "Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.",
            "inteligência artificial",
        ),
        (
            "Busque por computação quântica; em seguida, copie o título do resultado inicial para um editor.",
            "computação quântica",
        ),
        (
            "Procure energia limpa, então abra o editor e transcreva o cabeçalho do primeiro link.",
            "energia limpa",
        ),
    ],
)
def test_search_to_editor_is_not_collapsed_into_the_first_search_action(
    interpreter: SemanticGoalInterpreter, command: str, query: str
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.SEARCH_TO_EDITOR
    assert intent.query == query
    assert intent.capabilities == ("web.search", "web.read", "text.edit")
    assert intent.plans == ()


@pytest.mark.parametrize(
    ("command", "accessible", "unavailable"),
    [
        (
            'Verifique se example.com está acessível. Se estiver, abra um editor e escreva "site acessível". Se não estiver, escreva "site indisponível".',
            "site acessível",
            "site indisponível",
        ),
        (
            "Teste se https://example.org está online; caso esteja, digite 'servidor ativo'; caso contrário, digite 'servidor inativo'.",
            "servidor ativo",
            "servidor inativo",
        ),
    ],
)
def test_conditional_site_extracts_both_branches_without_materializing_either(
    interpreter: SemanticGoalInterpreter,
    command: str,
    accessible: str,
    unavailable: str,
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.CONDITIONAL_SITE
    assert intent.url is not None
    assert intent.true_text == accessible
    assert intent.false_text == unavailable
    assert intent.plans == ()


def test_existing_single_action_can_delegate_to_policy(
    interpreter: SemanticGoalInterpreter,
) -> None:
    intent = interpreter.interpret("capturar tela")

    assert intent.kind is IntentKind.DETERMINISTIC
    assert intent.plans == (Plan("capture_screen", "screen"),)


def test_unknown_intent_is_left_for_the_general_planner(
    interpreter: SemanticGoalInterpreter,
) -> None:
    intent = interpreter.interpret("Organize meu dia da melhor maneira possível")

    assert intent.kind is IntentKind.GENERIC
    assert intent.plans == ()


@pytest.mark.parametrize(
    "command",
    [
        "Abra a calculadora e formate o disco",
        "Abra a calculadora e compacte a pasta",
        "Abra a calculadora e compre um ingresso",
        "Abra a calculadora e renomeie um arquivo",
        "Abra a calculadora e faça login",
        "Abra a calculadora e toque música",
        "Abra a calculadora e dê reboot",
        "Abra o VS Code e faça backup do projeto",
        "Abra o editor, escreva 'oi' e envie um email",
        "Abra a calculadora e apague meus arquivos",
        "Pesquise gatos; faça login",
        "Pesquise gatos; compre um produto",
        "Abra o editor e escreva oi; faça login",
        "Quero saber o significado de Josiel; pague uma conta",
        "Pesquise gatos e role para baixo",
        "Abra o editor e escreva oi e role para baixo",
    ],
)
def test_fast_paths_fail_closed_when_a_material_clause_is_uncovered(
    interpreter: SemanticGoalInterpreter,
    command: str,
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.GENERIC
    assert intent.plans == ()


@pytest.mark.parametrize(
    "command",
    [
        "Abra a calculadora e abra o navegador",
        "Abra o VS Code e abra o editor",
        "Pesquise gatos e pesquise cães",
        "Abra o editor e escreva 'a' e escreva 'b'",
        "Abra a calculadora e execute malware",
    ],
)
def test_fast_path_preserves_effect_cardinality_and_order(
    interpreter: SemanticGoalInterpreter,
    command: str,
) -> None:
    assert interpreter.interpret(command).kind is IntentKind.GENERIC


def test_code_editor_open_does_not_discard_a_requested_write_effect(
    interpreter: SemanticGoalInterpreter,
) -> None:
    intent = interpreter.interpret("Abra o VS Code e escreva 'Olá mundo'")

    assert intent.kind is IntentKind.GENERIC


@pytest.mark.parametrize(
    "command",
    [
        "Quero fazer uma anotação e escreva Olá",
        "Preciso fazer uma anotação e digite segredo",
    ],
)
def test_note_readiness_never_discards_explicit_write_effect(
    interpreter: SemanticGoalInterpreter,
    command: str,
) -> None:
    assert interpreter.interpret(command).kind is IntentKind.GENERIC


def test_conjunction_inside_search_content_is_not_mistaken_for_an_action_clause(
    interpreter: SemanticGoalInterpreter,
) -> None:
    intent = interpreter.interpret("Pesquise saúde e qualidade de vida")

    assert intent.kind is IntentKind.SEARCH
    assert intent.query == "saúde e qualidade de vida"


def test_explicit_browser_search_without_site_keeps_the_browser_requirement(
    interpreter: SemanticGoalInterpreter,
) -> None:
    intent = interpreter.interpret("No Brave, pesquise inteligência artificial")

    assert intent.kind is IntentKind.NAMED_BROWSER_SEARCH
    assert intent.browser == "brave-browser"


@pytest.mark.parametrize(
    ("command", "expected_kind"),
    [
        ("No Brave, pesquise gatos", IntentKind.NAMED_BROWSER_SEARCH),
        (
            "Abra o Brave, acesse google.com e pesquise gatos",
            IntentKind.NAMED_BROWSER_SEARCH,
        ),
        (
            "Abra o Brave, acesse example.com e pesquise gatos",
            IntentKind.GENERIC,
        ),
    ],
)
def test_named_browser_search_never_discards_an_explicit_site(
    interpreter: SemanticGoalInterpreter,
    command: str,
    expected_kind: IntentKind,
) -> None:
    assert interpreter.interpret(command).kind is expected_kind


@pytest.mark.parametrize(
    ("command", "query"),
    [
        ("Pesquise Firefox segurança", "Firefox segurança"),
        ("Pesquise Brave browser download", "Brave browser download"),
    ],
)
def test_browser_name_inside_query_is_subject_not_requested_application(
    interpreter: SemanticGoalInterpreter,
    command: str,
    query: str,
) -> None:
    intent = interpreter.interpret(command)

    assert intent.kind is IntentKind.SEARCH
    assert intent.browser is None
    assert intent.query == query


def test_named_browser_url_without_observable_bridge_fails_closed(
    interpreter: SemanticGoalInterpreter,
) -> None:
    intent = interpreter.interpret("Abra o navegador Brave e acesse globo.com")

    assert intent.kind is IntentKind.GENERIC


@pytest.mark.parametrize(
    "command",
    [
        "Somar 2 + 2",
        "Quero somar 2 + 2",
        "Preciso calcular 2 + 2",
        "Calcular 2 + 2",
    ],
)
def test_explicit_calculation_requires_result_evidence_not_only_tool_readiness(
    interpreter: SemanticGoalInterpreter,
    command: str,
) -> None:
    assert interpreter.interpret(command).kind is IntentKind.GENERIC


def test_goal_intent_kind_alias_is_stable() -> None:
    assert GoalIntentKind is IntentKind
