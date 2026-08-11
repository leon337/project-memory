# NEXT

## 1. Definir a próxima fase de implementação

PM-DURABLE-JOURNAL-001 e a restauração do ambiente local estão concluídas. Nenhum checkpoint físico do Durable Journal permanece pendente.

O próximo passo é Leandro escolher qual capacidade, comportamento ou limitação real do Robô será atacada na próxima fase. Não iniciar nova implementação antes dessa definição.

## 2. Preservar as garantias já comprovadas

Qualquer próxima fase deve manter as garantias vigentes: Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente e GoalVerifier como única autoridade de conclusão. Se uma capacidade futura precisar repetir legitimamente duas ações físicas idênticas na mesma task, ela deve introduzir identidade durável explícita em vez de usar contador implícito de retry/reclaim.
