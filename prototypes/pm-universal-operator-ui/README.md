# PM Universal Operator UI — protótipo local

Protótipo visual estático da RC 3.5 da `PM-UNIVERSAL-OPERATOR-001`.

## Objetivo

Materializar arquitetura de informação, estados críticos e hierarquia visual do futuro Painel sem depender de Figma ou outra ferramenta externa com cota de uso.

O protótipo preserva a Home V4.1 como referência visual e testa principalmente:

- objetivo atual e progresso por etapas;
- distinção entre ação executada e resultado comprovado;
- estados de execução, verificação, recovery, falha segura e sucesso comprovado;
- camada principal simples e detalhes técnicos em drawer secundário;
- status de conexões sem exposição de segredo;
- acessibilidade básica, teclado, responsividade e `prefers-reduced-motion`.

## Arquivos

- `index.html` — estrutura semântica da tela;
- `styles.css` — visual, responsividade e estados;
- `app.js` — interação local para alternar estados de demonstração e abrir detalhes técnicos.

## Como abrir

Não há build, framework ou dependência externa.

Abra `index.html` diretamente no navegador ou sirva esta pasta com qualquer servidor HTTP local simples.

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
