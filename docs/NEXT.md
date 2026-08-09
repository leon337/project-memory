# NEXT

## 1. Preservar metadados seguros também nas falhas de política

O teste físico mostrou que falhas anteriores à execução perdem provider, rota, fallbacks, ação e target canônico. Registrar esses metadados seguros antes da Policy Layer, sem persistir prompt bruto, resposta livre ou credenciais.

## 2. Validar a semântica do plano ainda dentro do fallback

`StructuredAction` valida a forma, mas alguns pares ação/target podem continuar semanticamente inválidos, como URL sem esquema ou aplicativo desconhecido. Fazer o router considerar esse caso uma falha de planejamento antes de declarar sucesso do provider, sem executar nem repetir ação física.

## 3. Ativar Cloudflare e tornar quotas/retries observáveis

Obter/configurar o `CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID`, validar o terceiro provider e tornar explícitos os limites e retries reais de cada SDK. No `google-genai` instalado, `HttpRetryOptions(attempts=1)` não adiciona uma tentativa extra; a proteção contra repetição de ação física deve continuar separada do retry de planejamento.
