# PM-HOME-IMPLEMENT-001 — Patrícia — Análise de Flakiness Física

## agent
Patrícia — Debugging e Análise de Falhas.

## input
Evidência física de LEANDRO com uma execução final `PASS_GATE: HOME_V4_1_PHYSICAL` precedida por dois modos de falha intermitente em execuções controladas.

## finding_focus
`FOCUS-RACE-001`

Sintoma:
`GoalExecutionFailed: RuntimeError: O foco mudou para outra janela desde a última ação preparada.`

Análise:
- o focus guard fez fail-closed corretamente e não digitou em uma janela inesperada;
- LEANDRO informou que não interferiu manualmente no computador durante a execução controlada;
- o caminho físico passou em execução posterior, indicando condição temporal/transiente, não corrupção permanente do parser `exatamente:`;
- o backend atual registra a primeira janela que assume foco após `open_application` e recusa `type_text` se o X11 reportar outro window id depois; uma troca de janela transitória durante a inicialização do editor é hipótese técnica plausível, mas ainda não deve ser tratada como causa provada sem nova reprodução instrumentada.

Decisão:
`MONITOR_AND_REGRESSION_REQUIRED` — não enfraquecer o focus guard. Qualquer correção deve preservar fail-closed e só aceitar uma janela final estabilizada/identificada.

## finding_conversation
`CONVERSATION-IDENTITY-001`

Sintoma:
o validador perguntou `Em qual projeto você está? Responda apenas o nome do projeto.` e recebeu `Robô Operador — MVP 0.3` em uma execução; a execução seguinte respondeu corretamente `project-memory`.

Análise:
- o system prompt contém `project-memory`, mas o contexto também pode conter títulos de produto como `Robô Operador — MVP 0.3`;
- o serviço atual aceita a primeira resposta textual não vazia de um provider sem validar contradição com fatos canônicos conhecidos;
- portanto existe uma fronteira real de grounding que pode ser endurecida sem simular IA: rejeitar resposta incompatível com a identidade canônica e usar fallback/correção de provider.

Decisão:
`REQUEST_CHANGES` para a fronteira conversacional antes da integração final.

## overall
O PASS físico final é válido e prova o caminho ponta a ponta. Porém o conjunto de evidências é `PASS_WITH_FLAKINESS`, não `PASS_STABLE`.

## handoff
Patrícia → Tiago/Rafael/Renato.

Próxima ação: criar regressões para identidade canônica e estabilidade de foco; corrigir somente o que for reproduzível sem reduzir proteções; executar CI e novo smoke físico dirigido.