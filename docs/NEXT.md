# NEXT

## 1. Adicionar journal durável para a janela residual de crash

O heartbeat impede expiração/reclaim enquanto o Robô está vivo, mas um crash abrupto depois de uma ação física e antes do ACK ainda pode permitir replay quando a task for reclamada.

Evoluir para journal/idempotência persistente por `task_id + action_key`, sem enfraquecer lease, Policy, FAILSAFE ou Emergency Stop.

O próximo passo exato é mapear onde cada ação física recebe sua identidade estável, onde o receipt é produzido e onde o ACK final da Central ocorre, para então definir o contrato mínimo do journal antes de alterar o executor.

## 2. Expandir capabilities e replanning somente com contratos verificáveis

Novas capacidades e variações semânticas devem entrar com decomposição lossless, grounding local, critérios explícitos, percepção independente e regressões adversariais, sem repetir operações físicas não idempotentes.
