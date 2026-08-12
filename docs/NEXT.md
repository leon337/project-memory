# NEXT

## 1. Continuar a RC física da segunda revisão a partir do estado `verifying`

A segunda revisão de `prototypes/pm-universal-operator-ui/` já foi sincronizada, validada e reaberta no host Linux. O estado inicial `executing` foi inspecionado fisicamente no Firefox com zoom de 110% e confirmou a correção semântica principal: `40%`, `2 de 5 comprovadas` e `Etapa atual: 3 de 5` aparecem como informações distintas.

A Home também deixou de expor permanentemente capability, rota, journal, lease e recovery, e o bloco de conexões não ocupa mais a área principal do objetivo. Esse primeiro estado passa na inspeção inicial, mas isso ainda não fecha a RC visual inteira.

O próximo teste físico é alternar o protótipo para `Verificando` e confirmar que o progresso comprovado permanece em 40%, a etapa atual continua 3 de 5 e a linguagem visual deixa claro que execução técnica não equivale a resultado comprovado.

## 2. Concluir a RC visual e decidir a RC 3.5

Depois de `verifying`, auditar um estado por vez: `recovering`, falha segura e `succeeded`, além do drawer `Detalhes técnicos`, responsividade, zoom, hierarquia visual, acessibilidade e clareza.

Confirmar especialmente que estados ainda não comprovados não avançam além de `40%`, que `succeeded` só chega a `100%` quando as cinco etapas aparecem comprovadas, que os detalhes técnicos permanecem em camada secundária e que a escala baseada em `rem`, `%`, `fr`, `clamp()` e `minmax()` mantém consistência em diferentes tamanhos de tela.

Depois dessa auditoria, aprovar, modificar ou rejeitar as conclusões da RC 3.5. A arquitetura operacional ainda não deve ser alterada antes dessa decisão.

## 3. Realizar a quarta rodada e converter o desenho aprovado em contrato executável

Somente após a aprovação da RC 3.5 e da arquitetura de informação materializada no protótipo local, realizar a quarta rodada para congelar os contratos do primeiro slice Git/GitHub sandbox e transformar o resultado em issue/missão implementável, com critérios de aceitação, capacidades, sequência de entrega, testes e evidências exigidas.

Toda nova capacidade deve preservar Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente, EvidenceRecord e GoalVerifier como única autoridade de conclusão. A identidade durável de efeitos externos não pode permitir replay cego entre rotas ou retries/reclaims.
