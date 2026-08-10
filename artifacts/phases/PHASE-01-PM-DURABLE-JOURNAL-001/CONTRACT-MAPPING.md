# CONTRACT MAPPING

1. Task identity: `TaskStore.id` UUID.
2. Action identity: antes desta missão não havia identidade durável; havia apenas action keys em memória no Goal Runtime.
3. Preparação: `_execute_observed_step` avalia Policy antes de `executor.execute`.
4. Policy: `policy.evaluate_plan`.
5. Ownership: `LeaseHeartbeat` + `LeaseGuardedExecutor`.
6. Chamada física: `ActionExecutor.execute` → Playwright/Desktop backend.
7. Receipt: dict técnico retornado por `ActionExecutor` e registrado como `EvidenceKind.EXECUTION_RECEIPT`.
8. Percepção independente: browser/application/readback/active-window observers.
9. EvidenceRecord: criado no Goal Runtime e ligado a critério/step.
10. GoalVerifier: única autoridade de conclusão.
11. Resultado à Central: POST `/api/agent/tasks/{task_id}/result`.
12. Aceite da Central: `TaskStore.complete_task` exige lease vigente.
13. ACK: resposta terminal aceita pela Central.
14. Session context: commit somente depois desse ACK.
15. Reclaim: expired running volta a queued quando seguro e attempts permitem.
16. Idempotência: antes da missão era principalmente proteção in-process; não havia prova durável entre processos.

Conclusão do mapping: a fronteira mínima correta está em torno de `LeaseGuardedExecutor.execute`, com persistência na Central antes da entrada física e antes do ACK terminal.
