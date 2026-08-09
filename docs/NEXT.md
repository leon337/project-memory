# NEXT

## 1. Integrar o Goal Runtime universal no Robô real

Usar `docs/CODEX_GOAL_RUNTIME_MISSION.md` como contrato de execução.

A fundação já existe em:

- `src/context_anchor/goal_runtime.py`;
- `tests/test_goal_runtime_contract.py`.

Integrar essa fundação ao `local_agent.py` para que **todo** pedido — determinístico simples, sequência local ou IA — passe pelo mesmo `GoalRunState` e pelo mesmo `GoalVerifier` antes de poder terminar `succeeded`.

Critério de conclusão:

- nenhum caminho de `execute_command()` consegue marcar objetivo completo fora do verifier;
- `ExecutionReceipt` isolado não prova conclusão;
- `finish` do planner não encerra um Goal com critérios pendentes;
- suíte completa verde.

## 2. Completar percepção, capabilities e autonomia até passar os testes físicos da missão

Implementar o necessário para atingir os critérios A–E de `docs/CODEX_GOAL_RUNTIME_MISSION.md`, incluindo:

- percepção estruturada de browser para ler resultados e extrair artefatos;
- resolução de capacidades/ferramentas reais;
- interpretação/decomposição semântica sem regex por frase como estratégia principal;
- dataflow entre subobjetivos;
- contexto operacional curto entre tasks;
- replanning, budgets e detecção de falta de progresso.

Não considerar concluído apenas com testes mockados: executar e repetir os testes físicos no Linux/X11 até os critérios serem satisfeitos ou existir bloqueio externo comprovável.

## 3. Fechar a missão com evidências e memória atualizada

Antes de encerrar:

- regressões físicas antigas continuam PASS;
- caso crítico `pesquise → leia primeiro resultado → editor → escreva título` passa de ponta a ponta;
- objetivo condicional real passa;
- continuidade contextual entre tasks passa;
- nenhum falso `succeeded` conhecido;
- suíte completa, compilação e `git diff --check` passam;
- alterações corretas são commitadas e publicadas em `main`;
- `STATUS.md`, `ARCHITECTURE.md`, `DECISIONS.md` e este `NEXT.md` refletem a realidade verificável final.
