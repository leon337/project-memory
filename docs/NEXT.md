# NEXT

## 1. Manter a bateria de regressão ligada a mudanças do desktop/browser

Reexecutar os casos físicos afetados quando houver mudança relevante em X11, AT-SPI, Playwright, browser, capability discovery ou proteção de foco.

O gate continua sendo o estado final observado e os critérios do GoalVerifier; screenshot ou receipt isolado não substituem evidência estruturada.

## 2. Adicionar journal durável para a janela residual de crash

O heartbeat impede expiração/reclaim enquanto o Robô está vivo, mas um crash abrupto depois de uma ação física e antes do ACK ainda pode permitir replay quando a task for reclamada.

Evoluir para journal/idempotência persistente por `task_id` + `action_key`, sem enfraquecer lease, Policy, FAILSAFE ou Emergency Stop.

## 3. Expandir capabilities e replanning somente com contratos verificáveis

Novas capacidades e variações semânticas devem entrar com decomposição lossless, grounding local, critérios explícitos, percepção independente e regressões adversariais.

Priorizar alternativas recuperáveis por step e ampliar replanning estruturado sem repetir operações físicas não idempotentes.
