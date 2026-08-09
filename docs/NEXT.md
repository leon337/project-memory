# NEXT

## 1. Integrar a fundação do Goal Runtime ao `local_agent`

A fundação isolada já existe em `src/context_anchor/goal_runtime.py` com contratos, Evidence Ledger básico e Goal Verifier determinístico. Os testes de contrato estão em `tests/test_goal_runtime_contract.py`.

Agora fazer a refatoração pesada:

- todo pedido cria um `GoalRunState`;
- fast paths deixam de retornar sucesso diretamente e passam a produzir steps/evidências dentro do Goal Run;
- planner por IA sugere próxima ação, mas não declara sucesso;
- separar `ExecutionReceipt` de observação/evidência;
- somente `GoalVerifier` autoriza o verdict final;
- manter compatibilidade com quotas, fallback de providers, Policy Layer, FAILSAFE, Emergency Stop e telemetria.

Regressão obrigatória:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

Não pode concluir enquanto houver critério obrigatório pendente.

## 2. Adicionar percepção estruturada suficiente para provar efeitos

Prioridade:

- browser: URL, status, título, DOM/texto, links e resultados de busca estruturados;
- desktop: janela/processo e depois accessibility/AT-SPI para readback de conteúdo;
- ligar observações a `EvidenceRecord`;
- evitar screenshot/visão multimodal como caminho padrão quando DOM/acessibilidade bastarem.

Critério físico principal: pesquisar um termo, obter o título real do primeiro resultado, transferi-lo ao editor e comprovar o conteúdo escrito.

## 3. Evoluir autonomia sem depender de frases cadastradas

Depois do runtime/verificação:

- Capability Catalog/Resolver (`text.edit`, `calculate`, `browser.search`, `browser.read`, etc.);
- descoberta dinâmica de aplicativos por PATH, `.desktop`, MIME e metadados;
- interpretação/decomposição semântica de linguagem natural;
- Session Context curto entre tasks;
- Recovery Manager com budgets, no-progress e estratégia alternativa;
- primeiro objetivo condicional real com branch comprovada por evidência.
