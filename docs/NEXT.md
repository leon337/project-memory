# NEXT

## 1. Executar RC pré-quarta rodada da `PM-UNIVERSAL-OPERATOR-001`

Antes de congelar arquitetura ou transformar o planejamento em contrato de implementação, executar uma rodada de crítica e refinamento sobre a arquitetura V3 e sobre a experiência operacional do Painel atual.

A RC deve cobrir principalmente:

- arquitetura e engenharia: necessidade e fronteiras do Durable Execution Manifest, identidade de efeito versus execução, Capability Registry, Execution Route Resolver, adapters, Credential Broker, recovery, persistência, versionamento, Policy, lease/journal, observabilidade e risco de overengineering;
- segurança e qualidade: ambiguity/replay, prompt injection indireta, privilégios mínimos, tratamento de credenciais, contratos de observação/verificação e estratégia de testes/fault injection;
- UI/UX/design: arquitetura de informação, fluxo Conversar versus Executar objetivo, acompanhamento visual de objetivo/subobjetivos/etapas, estados `planning/executing/verifying/blocked/recovery`, evidências, rota utilizada, credenciais sem exposição de segredo, erros/fail-closed, controles de emergência, acessibilidade, responsividade e redução de complexidade técnica para o usuário;
- convergência front-end/back-end: nenhum estado visual pode ser ilustrativo; toda informação mostrada no Painel deve possuir fonte real e contrato observável no runtime.

Não implementar código nem congelar a arquitetura durante esta RC.

## 2. Consolidar as conclusões da RC para aprovação humana

Depois da RC, apresentar as mudanças propostas sobre a arquitetura V3, os riscos encontrados, os pontos descartados por overengineering, a arquitetura de informação candidata do Painel e os critérios de UX/observabilidade. Somente decisões explicitamente aprovadas devem entrar em `ARCHITECTURE.md` e `DECISIONS.md`.

## 3. Realizar a quarta rodada e converter o desenho aprovado em contrato executável

Somente após a aprovação da RC, realizar a quarta rodada para congelar os contratos do primeiro slice de Git/GitHub sandbox e transformar o resultado em issue/missão implementável, com critérios de aceitação, capacidades, sequência de entrega, testes e evidências exigidas.

Toda nova capacidade deve preservar Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente, EvidenceRecord e GoalVerifier como única autoridade de conclusão. A identidade durável de efeitos externos não pode permitir replay cego entre rotas ou retries/reclaims.
