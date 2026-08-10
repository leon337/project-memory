# PM-RELIABILITY-FOCUS-001 — Patrícia — Root Cause

## scope
Investigar `FOCUS-RACE-001` sem alterar a política fail-closed.

## evidence
No baseline `main@5cc1778523`, `PyAutoGuiDesktopBackend._wait_for_active_window_change()` encerra na primeira janela ativa diferente de `previous_window_id`, dorme 150 ms e devolve o XID observado sem uma segunda leitura pós-settling. `open_application()` usa esse XID como `_expected_window_id`. `type_text()` compara novamente o XID ativo e recusa teclado se ele mudou.

A falha física anterior ocorreu exatamente entre `open_application(editor)` e `type_text`, sem interação humana declarada, e depois passou em repetição.

## finding
Causa técnica candidata: corrida de startup X11. Uma superfície transitória do mesmo processo/aplicativo pode ser a primeira janela diferente, e a superfície final pode assumir foco depois de `_expected_window_id` já ter sido armado.

## constraints
- não aceitar troca arbitrária de XID;
- não desabilitar verificação por chunk;
- não reduzir FAILSAFE/Emergency Stop/lease/Policy;
- janela final deve ser estável e, quando conhecida, compatível com WM_CLASS do aplicativo solicitado.

## decision
`PASS_TO_ENGINEERING`

## handoff
Patrícia → Rafael: implementar estabilização antes do arming do teclado e preservar todos os guards posteriores.
