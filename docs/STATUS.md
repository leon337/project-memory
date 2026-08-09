# STATUS

## Objetivo atual

Construir um operador digital local capaz de receber objetivos em linguagem natural, descobrir capacidades disponíveis, executar em ciclo fechado e só encerrar quando o resultado final estiver comprovado por evidências.

## Estado verificável agora

O `main` continua no commit `b7f79a0e4830d37d763a46b981497b52519781b8` com o MVP anterior estável.

O trabalho pesado do novo Goal Runtime está preservado na branch:

`codex/goal-runtime-wip`

Checkpoint inicial:

`f73abddc23b676c990755011621a3a4b1db7b4f7`

Correção P0 mais recente:

`5894f98c0a1004a76bc10326a04a58e08b9807e0`

A branch está à frente de `main` e contém código/testes da missão sem incluir PNGs, PDFs, arquivos pessoais ou `egg-info`.

## Arquitetura nova já implementada na branch WIP

O fluxo local novo já está conectado:

```text
pedido
→ claim + lease
→ contexto operacional curto
→ interpretação local tipada ou decomposição estruturada por provider
→ GoalContract / GoalRunState
→ Capability Resolver
→ Policy Layer
→ executor físico
→ ExecutionReceipt
→ percepção independente
→ EvidenceRecord
→ GoalVerifier
→ continuar/falhar/succeeded
```

Componentes novos relevantes:

- `src/context_anchor/goal_execution.py` — orquestrador universal de Goal Runs;
- `src/context_anchor/capabilities.py` — resolução de capacidades para aplicativos instalados;
- `src/context_anchor/goal_interpreter.py` — interpretação tipada e fail-closed para cobertura incompleta;
- `src/context_anchor/session_context.py` — memória operacional curta com proveniência/TTL;
- `src/context_anchor/lease.py` — heartbeat e proteção de posse da task;
- `src/context_anchor/redaction.py` — sanitização de resultados/logs/contexto;
- `src/context_anchor/goal_runtime.py` — contratos, evidências, budgets e `GoalVerifier`.

`src/context_anchor/local_agent.py` já encaminha todo comando para `execute_goal()` na branch WIP.

## Regra de conclusão já travada em código

- `ExecutionReceipt` registra execução, mas não prova sozinho o efeito do objetivo;
- critérios obrigatórios precisam de observação/readback compatível;
- subobjetivos dependentes precisam estar satisfeitos;
- contratos sem critérios obrigatórios não concluem;
- `finish`/planner não possuem autoridade para encerrar objetivo incompleto;
- `GoalVerifier` é a autoridade final para `SUCCEEDED`.

## Autonomia já implementada em código

A branch WIP possui caminhos para:

- `Abra o VS Code` → capability `code.edit`;
- `Preciso fazer algumas contas.` → capability `calculate`;
- `Quero fazer uma anotação...` → capability `text.edit`;
- `Quero saber o significado do nome Josiel.` → busca + leitura estruturada;
- busca simples sem provider externo;
- busca em navegador explicitamente solicitado;
- pesquisa → observar primeiro resultado → extrair título → abrir editor → escrever → readback;
- objetivo condicional com observação de site e branch;
- contexto entre tasks, incluindo resolução de `lá` por artefato anterior.

A interpretação local continua conceitual/lexical e tipada; pedidos fora desse vocabulário vão para decomposição estruturada por provider. Não há pretensão de entendimento semântico aberto totalmente local nesta etapa.

## Regressão crítica histórica

Pedido:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

O falso PASS histórico é coberto agora por critérios separados de pesquisa, resultados, primeiro título, editor e readback do texto final. Automatizado, esse fluxo está implementado; validação física integrada pelo Painel/Central/Robô ainda é obrigatória antes do merge em `main`.

## P0 de cobertura de objetivo — corrigido

Foi encontrado um caso em que:

`Abra o Brave, acesse example.com e pesquise gatos`

poderia perder a URL explícita e virar uma busca em outro mecanismo.

O commit `5894f98c0a1004a76bc10326a04a58e08b9807e0` corrigiu isso:

- pesquisa em navegador nomeado sem site explícito continua fast path;
- Google/Bing/DuckDuckGo explícitos continuam fast path;
- site explícito não reconhecido como mecanismo de busca vai para `GENERIC`/fail-closed antes de qualquer ação física;
- regressão automatizada exige `executor.executed == []` no caso incorreto.

O Codex reportou `10 passed` nos testes focados dessa correção.

## Testes automatizados

No checkpoint anterior à correção P0, o Codex reportou suíte local completa com:

`333 passed, 1 warning`

Também foram reportadas várias suítes focadas verdes.

Depois da correção P0 foram reportados `10 passed` nos testes diretamente relacionados.

Ainda não existe execução de GitHub Actions para a branch WIP; portanto o estado da suíte completa dessa branch ainda precisa ser repetido antes do merge.

## Testes físicos integrados

Pelos critérios estritos de `docs/CODEX_GOAL_RUNTIME_MISSION.md`, a nova branch ainda não possui a bateria A–E totalmente aprovada pelo fluxo real Painel → Central → Robô.

Há provas físicas parciais/diretas de editor/readback, navegação, busca, fluxo pesquisa→título→editor, condicional e contexto, mas isso não substitui a validação integrada obrigatória.

## Providers

O modo multi continua com Z.AI/GLM, Google Gemini e Cloudflare Workers AI. Cloudflare ainda depende de `Account ID` no ambiente real. Z.AI/Gemini já apresentaram 429 em testes anteriores; fast paths e capabilities locais continuam importantes para preservar quota.

## Controles preservados

- Emergency Stop persistente;
- FAILSAFE físico;
- proteção de foco;
- Policy Layer;
- `shell=False`;
- leases da Central;
- credenciais fora de código/Git/logs;
- Painel/Central em localhost por padrão.

## Situação de conclusão

A missão **não está concluída** e a branch WIP **não deve ser mergeada em `main` ainda**.

O principal trabalho restante é validação física integrada, correção de qualquer falha real encontrada, repetição da suíte completa/checks e fechamento documental/merge somente após os critérios obrigatórios passarem.
