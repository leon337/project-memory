# NEXT

## 1. Ativar o planner multi-provider no Linux real com credenciais não expostas

O router e os adaptadores de **Z.AI, Cloudflare Workers AI e Gemini** já estão implementados no `main`, e a cópia local já foi atualizada com `git pull --ff-only`.

Durante a edição do `.env`, partes das chaves Z.AI e Gemini ficaram visíveis em um screenshot compartilhado na conversa. Antes do teste real, essas duas credenciais devem ser rotacionadas/substituídas localmente.

Próximos passos:

1. revogar/substituir as chaves Z.AI e Gemini expostas no screenshot;
2. atualizar o `.env` local, sem enviar screenshot do arquivo, mantendo:
   - `CONTEXT_ANCHOR_PLANNER_MODE=multi`;
   - `CONTEXT_ANCHOR_ZAI_API_KEY=<nova chave>`;
   - `CONTEXT_ANCHOR_GEMINI_API_KEY=<nova chave>`;
3. salvar o `.env`;
4. reiniciar o Robô pelo Painel;
5. enviar uma intenção simples que o parser determinístico não entenda, por exemplo `Por favor abra o editor de texto para mim`;
6. confirmar em tarefa/log que o resultado registra `planner_provider` e `planner_route` e que a ação continua passando pela Policy Layer.

Critério de conclusão: uma intenção em linguagem natural deve ser planejada por uma API real, convertida para uma única `StructuredAction`, executada pelo caminho físico já validado e registrada sem expor credenciais.

## 2. Adicionar Cloudflare ao router real e validar fallback

O token Workers AI já foi criado e guardado localmente. Falta obter/configurar `CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID`.

Depois:

1. adicionar `CONTEXT_ANCHOR_CLOUDFLARE_API_TOKEN` e `CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID` ao `.env`;
2. reiniciar o Robô;
3. confirmar que pedido simples prioriza Cloudflare e pedido condicional/reasoning prioriza Z.AI;
4. provocar de forma controlada uma indisponibilidade de provedor antes da execução e confirmar fallback para outro provedor sem repetir ação física.

## 3. Completar o quota manager e telemetria do router

Depois do primeiro teste real passar, ampliar o controle atual de RPM/cooldown para incluir, quando mensurável:

- budget diário de neurons do Cloudflare;
- quotas efetivas do Gemini;
- limites/feedback disponíveis do Z.AI;
- contadores locais conservadores onde não houver endpoint/header de quota;
- exposição no Painel de provedor usado, latência, cooldown e capacidade restante estimada.

A visão/multimodalidade e o loop autônomo multietapa entram somente depois desse caminho de ação única estar estável.
