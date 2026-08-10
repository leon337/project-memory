# PM-RELIABILITY-FOCUS-001 — Rafael — Implementação

## scope
Corrigir a preparação de foco do Robô Linux/X11.

## implementation
Criado `StableFocusDesktopBackend`, extensão de `PyAutoGuiDesktopBackend`.

Mudanças funcionais:
- novo XID precisa permanecer estável por 400 ms antes de ser armado;
- mudança de XID durante settling reinicia a contagem;
- aplicativos conhecidos exigem WM_CLASS compatível;
- janela não relacionada é ignorada durante startup;
- o caso sem XID ativo anterior também passa pela estabilização;
- aplicativos desconhecidos mantêm compatibilidade por XID estável;
- receipt de abertura recebe `window_class`, `app_identity_verified`, `focus_stable_for_seconds` e `focus_trace`;
- `local_agent.py` injeta o backend novo no caminho real do Robô.

## preserved invariants
`type_text()` continua herdando o guard original e verifica o XID antes do teclado e entre chunks. GoalVerifier, Policy, lease, Emergency Stop e FAILSAFE não foram alterados.

## evidence
- branch: `fix/focus-race-001`;
- PR: #5;
- código funcional coberto por regressões em `tests/test_focus_stability.py`.

## decision
`PASS_WITH_PHYSICAL_VALIDATION`

## handoff
Rafael → Renato: validar suíte integral e preparar smoke físico repetido.
