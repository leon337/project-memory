# PHASE-01 PLAN — PM-DURABLE-JOURNAL-001

## Classificação
Classe B — alteração de persistência, recovery, execução física e contratos entre Central/Robô.

## Objetivo
Impedir replay cego de ação física já iniciada/executada quando uma task é recuperada após crash/reclaim, preservando GoalVerifier, Policy, lease, FAILSAFE e Emergency Stop.

## Escopo
- mapear identidade de task/ação, executor, receipt, percepção, verifier, ACK e reclaim;
- criar journal durável correlacionado por `task_id + action_key`;
- fail-closed para estado físico ambíguo;
- migração compatível com SQLite existente;
- fault injection A–E;
- privacidade mínima no journal;
- retenção/cleanup somente após terminal ACK.

## Fora do escopo
- reescrever Goal Runtime;
- criar microserviço;
- substituir Policy/lease;
- inferir sucesso a partir do journal;
- publicar controle remoto.

## Gates
1. CONTRACT_MAPPING completo.
2. Contrato mínimo aprovado internamente.
3. Implementação + regressões.
4. CI verde.
5. revisão, auditoria e closeout.
