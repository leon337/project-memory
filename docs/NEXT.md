# NEXT

## 1. Revalidar fisicamente o Gemini com `response_json_schema`

Três testes reais com Z.AI + Gemini já ocorreram. O roteador fez fallback corretamente antes da execução física, mas ainda não houve uma `StructuredAction` bem-sucedida por API real.

Estado atual:

- Z.AI pode retornar `HTTP 429 / código 1305`, indicando rate limit/indisponibilidade transitória;
- Gemini usa o SDK oficial `google-genai` + `client.models.generate_content(...)`;
- modelo padrão: `gemini-3.6-flash`;
- o primeiro teste físico do SDK revelou `400 INVALID_ARGUMENT` porque `ACTION_SCHEMA` estava em `response_schema`;
- o adaptador foi corrigido para `response_json_schema=ACTION_SCHEMA`, que suporta o JSON Schema padrão usado pelo projeto;
- o teste automatizado confirma `response_schema is None`, `response_json_schema` ativo e `additionalProperties=False` preservado;
- Install, Compile e Test passaram no CI do commit `6efd18d55454749d75833db00948b8728115e146`.

Próximos passos:

1. executar `git pull --ff-only` na cópia local;
2. reiniciar o Robô pelo Painel;
3. repetir exatamente `Por favor abra o editor de texto para mim`;
4. confirmar se, após eventual `429` do Z.AI, Gemini gera `open_app → editor` e o Xed abre;
5. verificar nos logs o provedor usado, rota e provedores que falharam.

Critério de conclusão: pelo menos um provedor real deve gerar uma única `StructuredAction`, a ação deve passar pela Policy Layer e ser executada pelo caminho físico já validado.

## 2. Ativar Cloudflare como terceiro provedor e validar fallback

O token Workers AI já foi criado e guardado localmente. Falta obter/configurar `CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID`.

Depois:

1. adicionar `CONTEXT_ANCHOR_CLOUDFLARE_API_TOKEN` e `CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID` ao `.env`;
2. reiniciar o Robô;
3. confirmar que pedido simples prioriza Cloudflare e pedido condicional/reasoning prioriza Z.AI;
4. validar fallback para outro provedor sem repetir ação física.

## 3. Completar quota manager e telemetria do router

Depois do primeiro plano real passar, ampliar o controle atual para incluir, quando mensurável:

- budget diário de neurons do Cloudflare;
- quotas efetivas do Gemini;
- limites/feedback disponíveis do Z.AI;
- contadores locais conservadores onde não houver endpoint/header de quota;
- exposição no Painel de provedor usado, latência, cooldown e capacidade restante estimada.

A visão/multimodalidade e o loop autônomo multietapa entram somente depois desse caminho de ação única estar estável.
