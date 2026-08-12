# PM Universal Operator UI — protótipo local

Protótipo visual estático da RC 3.5 da `PM-UNIVERSAL-OPERATOR-001`.

## Objetivo

Materializar arquitetura de informação, estados críticos e hierarquia visual do futuro Painel sem depender de Figma ou outra ferramenta externa com cota de uso.

O protótipo preserva a Home V4.1 como referência visual e testa principalmente:

- objetivo atual e progresso por etapas;
- distinção entre ação executada e resultado comprovado;
- estados de execução, verificação, recovery, falha segura e sucesso comprovado;
- camada principal simples e detalhes técnicos em drawer secundário;
- acessibilidade básica, teclado, responsividade e `prefers-reduced-motion`.

## Arquivos

- `index.html` — estrutura semântica da tela;
- `styles.css` — visual, responsividade e estados;
- `app.js` — interação local para alternar estados de demonstração e abrir detalhes técnicos.

## Como abrir

Não há build, framework ou dependência externa.

Abra `index.html` diretamente no navegador ou sirva esta pasta com qualquer servidor HTTP local simples.

## Regra de medidas e consistência visual

A UI usa unidades relativas/responsivas como padrão para evitar uma tela calibrada para apenas uma resolução.

- `rem` para tipografia, espaçamentos, raios, dimensões mínimas e controles;
- `%` para proporções em relação ao contêiner;
- `fr` para distribuição em CSS Grid;
- `clamp()` para escalas que precisam crescer ou reduzir dentro de limites controlados;
- `minmax()` para manter painéis utilizáveis sem fixar largura rígida;
- `vw`, `vh`/`dvh` somente quando a dimensão precisa realmente acompanhar a viewport;
- `px` fica restrito a detalhes técnicos finos, como bordas de `1px`, quando isso for mais apropriado.

Breakpoints também são expressos em unidades relativas (`rem`). A regra vale para este protótipo e para a UI operacional futura, salvo necessidade técnica explicitamente justificada.

## Semântica do progresso

Posição no fluxo e progresso comprovado são informações diferentes.

Se a etapa atual é `3 de 5`, mas somente as etapas 1 e 2 possuem evidência suficiente, a interface mostra:

- `40%` de progresso comprovado;
- `2 de 5 comprovadas`;
- `Etapa atual: 3 de 5`.

Uma etapa em `executing`, `verifying`, `recovering` ou falha segura não aumenta o percentual comprovado. O percentual só avança quando o critério correspondente está efetivamente comprovado.

## Camada principal e detalhes técnicos

A Home principal prioriza objetivo, progresso comprovado, etapa atual, verificação, recovery/falha segura e evidência recente.

`capability`, rota, journal, lease, recovery técnico e referência de credencial ficam no drawer `Detalhes técnicos`. Status de conexões pertence à seção `Conexões`, em vez de ocupar espaço permanente durante a execução de um objetivo.

## Regra de fronteira com o produto real

Este diretório é **protótipo de design**. Os dados exibidos são simulados e o banner da tela informa isso explicitamente.

Nenhum estado visual daqui pode ser copiado para a Home operacional como se fosse real sem antes existir uma fonte estruturada no runtime/Central. Em particular, `planning`, `executing`, `verifying`, `recovering`, etapa atual, capability, rota, replay/recovery e evidências precisam de contratos observáveis reais.

O protótipo não altera Goal Runtime, TaskStore, Durable Action Journal, Policy, lease/heartbeat, FAILSAFE, Emergency Stop, EvidenceRecord nem GoalVerifier.

## Estados de demonstração

Os botões no rodapé simulam apenas para avaliação visual:

- `Executando`;
- `Verificando`;
- `Recuperando`;
- `Falha segura`;
- `Comprovado`.

A implementação real não deve inferir esses estados lendo logs. A quarta rodada deverá definir a telemetria estruturada mínima que alimentará a UI operacional.
