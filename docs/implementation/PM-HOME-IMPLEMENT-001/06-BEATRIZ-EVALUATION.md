# PM-HOME-IMPLEMENT-001 — Beatriz — Avaliação de Agentes

## agent
Beatriz — Avaliação de Agentes.

## scope
Avaliar se a nova IA conversacional se comporta como conversa de projeto sem cruzar para execução.

## evaluation_contract
Os testes cobrem os seguintes critérios:
1. `Conversar` usa endpoint diferente de Task API;
2. mensagem de conversa não produz chamada `task:*` no controller;
3. resposta traz provider/modelo/context_version do backend que realmente respondeu;
4. contexto conhecido inclui `project-memory` quando solicitado;
5. mensagem e contexto com padrões de credencial são sanitizados antes do provider;
6. `Executar objetivo` continua usando `/api/tasks`;
7. Enter no campo principal permanece associado a Conversar;
8. execução exige botão explícito `Executar objetivo`;
9. GoalVerifier continua fora da autoridade da IA conversacional.

## evidence
- `tests/test_dashboard_v4_1.py`;
- `tests/test_conversation.py`;
- `tests/test_dashboard_browser_v4_1.py`;
- ciclo RED/GREEN de privacidade: runs 299/300;
- ciclo browser end-to-end controlado: run 305 capturou uma falha de infraestrutura de teste e foi corrigido sem alterar o comportamento esperado.

## verdict
`PASS_AS_AUTOMATED_EVALUATION`

A avaliação com provider real e contexto local do operador será executada pelo validador físico `scripts/validate_home_v4_1_physical.py`.

## artifact
Regressões comportamentais + este relatório.

## handoff
Beatriz → Júlia.

Entrega: contrato de comportamento verificável da IA.
Próxima ação: confirmar que a nova superfície não muda autoridade, identidade ou responsabilidade do Robô.
Critério: conversa não obtém capacidade operacional e nenhuma nova matéria reservada ao humano é criada.
