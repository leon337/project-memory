# PHASE PM-RELIABILITY-FOCUS-001 — PLAN

## Objective
Eliminar a corrida intermitente de foco Linux/X11 entre `open_application` e `type_text` sem remover nenhuma proteção fail-closed.

## Baseline
- repository: `leon337/project-memory`
- base: `main@5cc1778523daa6051ec0b7ab496f1b1f029110af`
- issue: #4
- branch: `fix/focus-race-001`
- PR: #5 draft

## Acceptance criteria
1. primeira superfície transitória não pode ser armada se o XID ainda estiver mudando;
2. app conhecido exige identidade WM_CLASS compatível;
3. janela não relacionada durante startup não vira alvo;
4. mudança real de foco após preparação continua recusando teclado;
5. suíte completa verde;
6. smoke físico: 5/5 execuções consecutivas `editor + escreva exatamente` com GoalVerifier `verified=true` e readback AT-SPI exato;
7. zero merge antes de auditoria e gate interno após evidência física.

## Safety invariants
Emergency Stop, FAILSAFE, Policy, lease e GoalVerifier permanecem inalterados.
