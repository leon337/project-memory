# NEXT

## 1. Auditar o drawer `Detalhes técnicos`

Os cinco estados críticos do protótipo (`executing`, `verifying`, `recovering`, falha segura e `succeeded`) já foram inspecionados fisicamente e passaram na semântica visual esperada. O próximo teste é abrir `Detalhes técnicos` e confirmar que capability, rota, journal, lease, recovery e referência de credencial aparecem somente nessa camada secundária, sem segredo real, sem sobreposição incorreta e com fechamento funcional por botão, backdrop e `Esc` quando aplicável.

## 2. Auditar responsividade, zoom, acessibilidade e clareza final

Depois do drawer, testar a mesma Home em tamanhos de viewport menores e maiores e em níveis de zoom diferentes. Confirmar que a escala baseada em `rem`, `%`, `fr`, `clamp()`, `minmax()` e unidades de viewport mantém hierarquia, legibilidade, controles utilizáveis e ausência de cortes/overflow indevido. Revisar também foco de teclado, contraste funcional, leitura sem depender somente de cor e clareza das mensagens de execução, verificação, recovery e falha segura.

## 3. Decidir a RC 3.5 e somente então realizar a quarta rodada

Com drawer e responsividade/acessibilidade aprovados, aprovar, modificar ou rejeitar a RC 3.5. Se aprovada, atualizar `ARCHITECTURE.md` e `DECISIONS.md` com a arquitetura vigente e então realizar a quarta rodada para congelar os contratos do primeiro slice Git/GitHub sandbox e transformá-los em missão implementável com critérios de aceitação, capacidades, sequência de entrega, testes e evidências exigidas. Toda nova capacidade deve preservar Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente, EvidenceRecord e GoalVerifier como única autoridade de conclusão, sem replay cego entre rotas ou retries/reclaims.
