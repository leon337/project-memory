# NEXT

## 1. Inverter a política local para permissiva por padrão

Substituir o modelo atual de allowlist por **permitir por padrão** dentro das permissões reais do usuário e do sistema operacional. Aplicativos, executáveis, shell/processos, argumentos e demais capacidades locais não devem depender de cadastro prévio. Criar uma denylist/regras de bloqueio para exceções que o usuário decidir proibir depois. Manter FAILSAFE, parada de emergência, telemetria e limites impostos pelo próprio sistema operacional.

## 2. Implementar o primeiro loop multi-etapa orientado por objetivo

Corrigir a diferença entre “uma ação terminou” e “o objetivo foi concluído”. O caso físico `Abra o editor de texto e escreva Olá mundo` abriu o editor, mas não digitou, embora a task tenha sido marcada `succeeded`. O Robô deve executar → observar/verificar → raciocinar novamente → escolher a próxima ação até concluir ou falhar explicitamente.

## 3. Retomar observabilidade do router e terceiro provider

Depois dos dois pontos acima, preservar metadados seguros também em falhas, validar semântica antes da execução e ativar Cloudflare Workers AI com `Account ID`, quotas e retries observáveis.
