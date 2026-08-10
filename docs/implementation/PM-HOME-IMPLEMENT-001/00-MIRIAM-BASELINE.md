# PM-HOME-IMPLEMENT-001 — Miriam — Baseline e Continuidade

## agent
Miriam — Memória e Gestão do Conhecimento.

## scope
Reconstruir a entrada da missão funcional a partir do estado verificável do projeto e da revisão encerrada `PM-HOME-REVIEW-001`.

## evidence
- MCF `main`: `1c58b4ba280bd32f587c2f042e35a2dba1a123a9`.
- project-memory `main`: `48712501f7d0ebc7e73e1be64d101ee40dd7aa5e`.
- Issue de revisão `#1`: encerrada como `completed`.
- Especificação de entrada: `docs/reviews/PM-HOME-REVIEW-001/25-CARMEM-FINAL-HOME-SPEC.md` na branch documental da revisão.
- Gate da revisão: `29-LEO-FINAL-GATE.md`, decisão `APROVAR` para fechar a fase documental.
- Nova Issue funcional: `#2`.
- Branch funcional: `feat/pm-home-v4-1-implementation`, criada do SHA exato da `main`.
- PR funcional: `#3`, aberto como draft.

## state_reconciled
A revisão V4.1 é entrada reutilizável; não é prova de implementação. O Goal Runtime já está integrado e continua sendo a autoridade operacional vigente por meio do GoalVerifier. O finding `exatamente:` e o drift do README passam da revisão para a implementação como trabalho concreto.

## decision
`PASS`

## artifact
Este arquivo.

## handoff
Miriam → Rafael.

Entrega: baseline, especificação V4.1 e findings transferidos sem reabrir decisões já encerradas.
Próxima ação: iniciar a implementação pelo teste regressivo `exatamente:`.
Critério: reproduzir a falha antes da correção e preservar o objetivo global da Home V4.1.
