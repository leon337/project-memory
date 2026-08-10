# PM-RELIABILITY-FOCUS-001 — Renato — Validação Automatizada

## scope
Validar regressões de foco e suíte completa antes do Linux/X11 físico.

## tests
`tests/test_focus_stability.py` cobre:
1. janela transitória do mesmo app → aguardar XID final;
2. `open_application()` arma somente o XID final estável;
3. janela transitória de outro app é ignorada;
4. somente janela incompatível para app conhecido → fail-closed;
5. ausência de XID anterior ainda exige identidade/estabilidade;
6. app desconhecido mantém comportamento genérico estável;
7. mudança real de foco depois do arming continua recusando teclado.

## CI evidence
- run 350 / `31406398505`: FAILURE de wiring (`ModuleNotFoundError`) antes da criação do módulo; não classificado como RED comportamental isolado;
- run 351 / `31406513548`: SUCCESS, `367 passed`;
- run 354 / `31407005939`: SUCCESS, `370 passed`, compilação PASS.

## physical validator
`scripts/validate_focus_stability_physical.py` exige 5 rodadas consecutivas. Cada rodada cria uma task real `editor + escreva exatamente`, exige `goal_completed=true`, `verified=true` e readback AT-SPI exato. Marcador final esperado: `PASS_GATE: FOCUS_STABILITY_PHYSICAL`.

## decision
`PASS_AUTOMATED_PENDING_PHYSICAL`

## handoff
Renato → Ricardo/Vinícius e depois ambiente físico Linux/X11.
