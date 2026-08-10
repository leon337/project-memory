# REPORT — PM-DURABLE-JOURNAL-001

A missão partiu do código real da `main` e da Issue #8. O risco confirmado era a janela `efeito físico → crash → ACK ausente → lease expira → reclaim`.

## Resultado técnico
Foi introduzido `ActionJournalStore` no mesmo SQLite da Central, sem microserviço novo. A unidade persistente é `task_id + action_key`.

O ciclo mínimo é:

`prepared → in_flight → executed → acknowledged`

- `prepared`: row persistida; backend físico ainda não foi chamado;
- `in_flight`: persistido antes de entrar no backend; para ação não repetível é estado ambíguo e bloqueia replay;
- `executed`: backend retornou e apenas receipt mínimo sanitizado foi persistido; isso NÃO prova efeito;
- `acknowledged`: Central aceitou estado terminal da task; elegível a cleanup por retenção.

`action_key` usa fingerprint BLAKE2 task-scoped de `action + target`; o target bruto não é persistido. Não há contador implícito de retry: a mesma ação+target não ganha uma segunda identidade só por ser tentada novamente.

Tasks antigas já iniciadas sem journal recebem fail-closed na migração. Task legada nunca iniciada (`queued`, attempts=0) pode ser reclamada sob journal v1.

A percepção independente e o GoalVerifier permanecem fora do journal e continuam sendo a única autoridade para `succeeded`.
