# NEXT

## 1. Criar a fundação do Goal Runtime universal

A decisão arquitetural está tomada: todo pedido deverá usar a mesma semântica de objetivo/conclusão, seja resolvido por fast path determinístico ou por IA.

Preparar primeiro a fundação leve antes da refatoração pesada:

- contratos tipados para Goal Contract, subobjetivos, critérios, artefatos e evidências;
- estado de execução do objetivo;
- Goal Verifier mínimo e determinístico;
- testes de contrato provando que ação executada não equivale a objetivo concluído;
- manter compatibilidade com o MVP enquanto a migração não termina.

Regressão principal: um objetivo composto não pode ser `succeeded` se ainda houver critério obrigatório pendente.

## 2. Migrar `local_agent` para usar o Goal Runtime em todos os caminhos

Depois da fundação, substituir a bifurcação semântica atual por um runtime comum:

- fast paths viram skills/etapas dentro do Goal Run;
- planner por IA sugere próxima etapa, mas não declara sucesso;
- Execution Receipt, observação e evidência ficam separados;
- somente o Goal Verifier autoriza o verdict final;
- manter quotas, fallback de providers, Policy Layer, FAILSAFE e Emergency Stop inalterados.

Regressão física obrigatória:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

Não pode concluir até pesquisar, obter o primeiro resultado, transferir o título ao editor e comprovar o resultado.

## 3. Evoluir percepção, capacidades e contexto operacional

Após o runtime comum estar estável:

- browser: DOM/texto/links/resultados estruturados;
- desktop: accessibility/AT-SPI antes de visão multimodal;
- capability resolver (`text.edit`, `calculate`, `browser.search`, `browser.read` etc.);
- descoberta dinâmica de aplicativos;
- Session Context curto entre tasks;
- Recovery Manager com budgets, no-progress e estratégias alternativas;
- primeiro objetivo condicional real com evidência de branch.
