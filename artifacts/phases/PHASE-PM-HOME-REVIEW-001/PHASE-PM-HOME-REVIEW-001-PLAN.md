# PHASE PM-HOME-REVIEW-001 — PLAN

## Objetivo
Revisar V1–V4 da Home do Robô e produzir uma especificação recomendada, multidisciplinar e auditável, sem alteração funcional nesta fase.

## Regra de execução vigente
Após correção explícita de LEANDRO, handoffs internos continuam automaticamente. HUMAN_GATE somente é aberto para matéria realmente reservada ao humano conforme protocolo MCF; nenhum gatilho desse tipo foi identificado até o checkpoint atual.

## Escopo
- Produto, experiência, UX, UI, acessibilidade;
- arquitetura, engenharia, segurança e IA;
- avaliação, governança, observabilidade e testes;
- rastreabilidade Git e auditoria;
- especificação final recomendada da Home V4.1.

## Fora de escopo
- implementação funcional da Home;
- alteração do Goal Runtime/GoalVerifier/Policy;
- alteração dos executores físicos;
- publicação remota do Painel.

## Baselines
- MCF main: `1c58b4ba280bd32f587c2f042e35a2dba1a123a9`
- project-memory main: `48712501f7d0ebc7e73e1be64d101ee40dd7aa5e`
- issue: #1
- branch: `review/pm-home-review-001`

## Critérios de aceite
- ESEV/handoffs contínuos e visíveis;
- comparação V1–V4;
- artefatos individuais dos especialistas necessários;
- especificação recomendada;
- Conversar vs Executar separados;
- telemetria real;
- GoalVerifier preservado;
- segurança, acessibilidade e testes definidos;
- Augusto valida mission trace;
- Emily audita independentemente;
- Léo decide gate interno;
- fechamento sem HUMAN_GATE artificial quando não houver matéria reservada a LEANDRO.

## Risco
Classe B — revisão documental sem mudança funcional.
