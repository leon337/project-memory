# NEXT

## 1. Aprovar, modificar ou rejeitar a RC 3.5 da `PM-UNIVERSAL-OPERATOR-001`

A crítica pré-quarta rodada de arquitetura, engenharia e UI/UX foi concluída como proposta e registrada em `STATUS.md`. Antes de alterar `ARCHITECTURE.md` ou `DECISIONS.md`, revisar principalmente:

- simplificação da arquitetura V3: evitar máquina de estados paralela para um Durable Execution Manifest e preferir evolução do journal/contrato durável existente;
- identidade semântica determinística de efeito, rota fixada antes do backend, recovery fail-closed e Credential Broker mínimo;
- Route Resolver determinístico e adapters tipados sem interface universal excessiva;
- arquitetura de informação do Painel: objetivo/progresso/verificação/recovery simples na superfície e detalhes técnicos em camada secundária;
- telemetria estruturada real para a UI, sem inferir estado a partir de logs e sem apresentar estados que o backend não possui.

## 2. Materializar e auditar o desenho visual antes da quarta rodada

Depois da aprovação conceitual da RC, produzir wireframes/telas de alta definição da Home do Operador Universal e dos estados críticos (`executing`, `verifying`, `recovering`, falha segura e detalhes técnicos), preservando a Home V4.1 como fundação. Cada elemento visual deve possuir uma fonte real prevista no runtime e nenhum segredo pode aparecer na interface.

## 3. Realizar a quarta rodada e converter o desenho aprovado em contrato executável

Somente após a aprovação da RC e da arquitetura de informação, realizar a quarta rodada para congelar os contratos do primeiro slice Git/GitHub sandbox e transformar o resultado em issue/missão implementável, com critérios de aceitação, capacidades, sequência de entrega, testes e evidências exigidas.

Toda nova capacidade deve preservar Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente, EvidenceRecord e GoalVerifier como única autoridade de conclusão. A identidade durável de efeitos externos não pode permitir replay cego entre rotas ou retries/reclaims.
