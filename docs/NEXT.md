# NEXT

## 1. Configurar e validar Cloudflare Workers AI como provider opcional

Obter `Account ID` e um API Token adequado diretamente na conta Cloudflare e salvar somente no `.env` local como `CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID` e `CONTEXT_ANCHOR_CLOUDFLARE_API_TOKEN`.

Depois validar uma conversa real e o fallback entre providers sem expor credenciais em Git, logs ou prompts. O suporte de código já existe; falta comprovar a configuração local.

## 2. Adicionar journal durável para a janela residual de crash

O heartbeat impede expiração/reclaim enquanto o Robô está vivo, mas um crash abrupto depois de uma ação física e antes do ACK ainda pode permitir replay quando a task for reclamada.

Evoluir para journal/idempotência persistente por `task_id + action_key`, sem enfraquecer lease, Policy, FAILSAFE ou Emergency Stop.

## 3. Expandir capabilities e replanning somente com contratos verificáveis

Novas capacidades e variações semânticas devem entrar com decomposição lossless, grounding local, critérios explícitos, percepção independente e regressões adversariais, sem repetir operações físicas não idempotentes.
