# DOMAIN ARCHITECTURE — DURABLE ACTION JOURNAL

```text
Goal Runtime
  ↓ Policy
LeaseGuardedExecutor
  ↓ journal.prepare(task_id, action_key)
Central / SQLite: PREPARED
  ↓ journal.transition(IN_FLIGHT)
backend físico/externo
  ↓ retorno técnico
journal.transition(EXECUTED, safe_receipt)
  ↓
percepção independente
  ↓ EvidenceRecord
GoalVerifier
  ↓ verdict final
Central complete_task
  ↓ ACK terminal
journal ACKNOWLEDGED
  ↓ retenção
cleanup
```

O journal não participa do verdict. Seu papel é exclusivamente provar histórico de tentativa/entrada/retorno suficiente para bloquear replay cego.
