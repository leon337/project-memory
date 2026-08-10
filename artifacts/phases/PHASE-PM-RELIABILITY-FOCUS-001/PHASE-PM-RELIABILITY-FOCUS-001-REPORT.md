# PHASE PM-RELIABILITY-FOCUS-001 — REPORT

## Resultado
A corrida intermitente de foco Linux/X11 foi tratada sem remover o comportamento fail-closed de teclado.

## Problema observado
Na validação física da Home V4.1, uma execução falhou entre `open_application(editor)` e `type_text` porque o XID ativo mudou sem interação humana declarada.

## Causa técnica
O backend antigo podia aceitar a primeira janela nova observada durante o startup e armar `_expected_window_id` antes de a superfície final do aplicativo estabilizar. Uma transição de superfície transitória para a janela final fazia o guard posterior interpretar a mudança como perda real de foco.

## Correção
`StableFocusDesktopBackend` passou a:
- aguardar estabilidade temporal do XID antes do arming;
- reiniciar settling quando o XID muda;
- validar WM_CLASS de aplicativos conhecidos;
- ignorar janela transitória não relacionada;
- manter apps desconhecidos por XID estável;
- preservar o guard de foco antes e entre chunks de teclado.

## Evidências automatizadas
- run 351: SUCCESS / 367 passed;
- run 354: SUCCESS / 370 passed;
- run 356: SUCCESS no checkpoint documental;
- Ricardo: `PASS_WITH_PHYSICAL_VALIDATION`;
- Vinícius: `PASS_WITH_REQUIREMENTS`.

## Evidência física final
A primeira tentativa foi contaminada por interação manual do operador e não foi usada como gate limpo.

Na segunda tentativa, sem interação manual:
- 5/5 rodadas consecutivas passaram;
- cada rodada terminou com GoalVerifier `verified=true`;
- cada rodada teve readback AT-SPI exato;
- marcador final: `PASS_GATE: FOCUS_STABILITY_PHYSICAL`.

Cada rodada abre um novo editor de propósito, para reexercitar startup e aquisição de foco.

## Gate
- Renato: `PASS_PHYSICAL_FINAL`;
- Emily: `PASS_FINAL`;
- Léo: `APROVAR`;
- HUMAN_GATE: `NOT_REQUIRED`;
- merge autorizado após CI verde do HEAD de closeout.
