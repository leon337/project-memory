# NEXT

## 1. Revalidar o planner multi-provider com Gemini Interactions

Dois testes reais com Z.AI + Gemini já ocorreram. O roteador fez fallback corretamente antes da execução física, mas ainda não houve uma `StructuredAction` bem-sucedida por API real.

Estado atual:

- Z.AI está retornando `HTTP 429 / código 1305`, classificado pelo próprio provedor como rate limit/indisponibilidade transitória;
- o adaptador Gemini foi migrado para a **Interactions API** atual;
- os testes automatizados dessa migração passaram no CI.

Próximos passos:

1. executar `git pull --ff-only` na cópia local;
2. reiniciar o Robô pelo Painel;
3. repetir exatamente `Por favor abra o editor de texto para mim`;
4. confirmar se, após eventual `429` do Z.AI, Gemini gera `open_app → editor` e o Xed abre;
5. verificar nos logs `planner_provider`, `planner_route` e provedores que falharam.

Critério de conclusão: pelo menos um provedor real deve gerar uma única `StructuredAction`, a ação deve passar pela Policy Layer e ser executada pelo caminho físico já validado.

## 2. Ativar Cloudflare como terceiro provedor e validar fallback

O token Workers AI já foi criado e guardado localmente. Falta obter/configurar `CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID`.

Depois:

1. adicionar `CONTEXT_ANCHOR_CLOUDFLARE_API_TOKEN` e `CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID` ao `.env`;
2. reiniciar o Robô;
3. confirmar que pedido simples prioriza Cloudflare e pedido condicional/reasoning prioriza Z.AI;
4. provocar de forma controlada uma indisponibilidade de provedor antes da execução e confirmar fallback para outro provedor sem repetir ação física.

## 3. Completar o quota manager e telemetria do router

Depois do primeiro plano real passar, ampliar o controle atual para incluir, quando mensurável:

- budget diário de neurons do Cloudflare;
- quotas efetivas do Gemini;
- limites/feedback disponíveis do Z.AI;
- contadores locais conservadores onde não houver endpoint/header de quota;
- exposição no Painel de provedor usado, latência, cooldown e capacidade restante estimada.

A visão/multimodalidade e o loop autônomo multietapa entram somente depois desse caminho de ação única estar estável.
