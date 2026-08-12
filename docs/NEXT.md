# NEXT

## 1. Sincronizar e revalidar a segunda revisão do protótipo no host

A `main` contém a segunda revisão de `prototypes/pm-universal-operator-ui/`, com progresso comprovado separado da etapa atual, detalhes técnicos movidos para drawer, conexões retiradas da Home, escala responsiva relativa e testes dedicados de proteção.

No host Linux, executar `atualizar-robo` e depois `validar-robo`. Só após ambos concluírem verdes, reabrir o protótipo no navegador e confirmar que a versão local corresponde à revisão nova.

## 2. Concluir a RC visual e decidir a RC 3.5

Auditar fisicamente os estados `executing`, `verifying`, `recovering`, falha segura e `succeeded`, o drawer `Detalhes técnicos`, responsividade, zoom, hierarquia visual, acessibilidade e clareza.

Confirmar especialmente que `Etapa atual: 3 de 5` não é confundida com percentual comprovado, que estados ainda não comprovados não avançam além de `40%`, que a Home não expõe capability/rota/journal/lease/recovery permanentemente e que a escala baseada em `rem`, `%`, `fr`, `clamp()` e `minmax()` mantém consistência em diferentes tamanhos de tela.

Depois dessa auditoria, aprovar, modificar ou rejeitar as conclusões da RC 3.5. A arquitetura operacional ainda não deve ser alterada antes dessa decisão.

## 3. Realizar a quarta rodada e converter o desenho aprovado em contrato executável

Somente após a aprovação da RC 3.5 e da arquitetura de informação materializada no protótipo local, realizar a quarta rodada para congelar os contratos do primeiro slice Git/GitHub sandbox e transformar o resultado em issue/missão implementável, com critérios de aceitação, capacidades, sequência de entrega, testes e evidências exigidas.

Toda nova capacidade deve preservar Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente, EvidenceRecord e GoalVerifier como única autoridade de conclusão. A identidade durável de efeitos externos não pode permitir replay cego entre rotas ou retries/reclaims.
