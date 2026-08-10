# PHASE PM-RELIABILITY-FOCUS-001

Missão de confiabilidade para eliminar a corrida de foco Linux/X11 observada entre abertura de aplicativo e digitação.

## Estado
`APROVADO_PARA_INTEGRACAO`

## Evidência principal
- CI automatizado: verde, incluindo 370 testes;
- smoke físico limpo: 5/5 rodadas consecutivas;
- GoalVerifier `verified=true` em todas;
- readback AT-SPI exato em todas;
- `PASS_GATE: FOCUS_STABILITY_PHYSICAL`.

## Segurança
A correção não remove o fail-closed. Mudança real de foco após arming continua bloqueando teclado.

## Rastreabilidade
- Issue #4
- PR #5
- branch `fix/focus-race-001`
