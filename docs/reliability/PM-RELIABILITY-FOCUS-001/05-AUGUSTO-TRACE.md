# PM-RELIABILITY-FOCUS-001 — Augusto — Mission Trace

## trace
1. baseline `main@5cc1778523daa6051ec0b7ab496f1b1f029110af` confirmado;
2. branch `fix/focus-race-001` criada;
3. Issue #4 promovida de débito aberto para missão ativa;
4. PR #5 draft criado;
5. hipótese de race XID revalidada no código;
6. run 350 falhou por wiring antes do módulo novo (`ModuleNotFoundError`);
7. backend estabilizado implementado;
8. run 351 passou com `367 passed`;
9. regressões reforçadas para `open_application`, fail-closed e ausência de XID anterior;
10. run 354 passou com `370 passed`;
11. Ricardo: `PASS_WITH_PHYSICAL_VALIDATION`;
12. Vinícius: `PASS_WITH_REQUIREMENTS`;
13. validador físico repetido versionado.

## audit note
O run 350 é mantido como falha real, porém não é falsamente apresentado como RED comportamental puro. A prova comportamental vem das regressões que modelam transição de XID e do smoke físico pendente.

## decision
`PASS_TO_EXTERNAL_PHYSICAL_VALIDATION`

## handoff
Augusto → Emily/Léo somente depois da evidência Linux/X11.
