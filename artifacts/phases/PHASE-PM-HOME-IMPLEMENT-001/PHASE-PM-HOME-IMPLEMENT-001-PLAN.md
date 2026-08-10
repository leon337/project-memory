# PHASE PM-HOME-IMPLEMENT-001 — PLAN

## Objetivo
Implementar a Home V4.1 do Painel do Robô preservando o GoalVerifier como autoridade final, separando tecnicamente `Conversar` de `Executar objetivo` e validando segurança, acessibilidade e comportamento.

## Classificação
`risk_class: C`

Motivo: mudança funcional em uma interface de sistema com autonomia/tool calling, controles operacionais e fronteira browser/localhost.

## Baselines
- MCF main: `1c58b4ba280bd32f587c2f042e35a2dba1a123a9`
- project-memory main: `48712501f7d0ebc7e73e1be64d101ee40dd7aa5e`
- Issue: `#2`
- Branch: `feat/pm-home-v4-1-implementation`
- PR: `#3` (draft)
- especificação de entrada: `PM-HOME-REVIEW-001`

## Escopo
1. TDD do modificador `exatamente:`.
2. Sincronizar README com Goal Runtime já integrado.
3. Implementar Home V4.1.
4. Implementar Conversation Service isolado.
5. Preservar Task API/Goal Runtime/GoalVerifier.
6. Implementar hardening browser/localhost.
7. Adicionar requisitos/regressões de acessibilidade.
8. Executar CI, Chromium, revisão de código, segurança e auditoria.
9. Executar validação física Linux/X11 quando o ambiente local estiver disponível.

## Fora de escopo
- alterar autoridade do GoalVerifier;
- remover Policy/Emergency Stop/FAILSAFE/foco/lease;
- publicar o Painel na Internet;
- implementar o journal durável de crash/replay nesta missão.

## Critérios de aceite
- `exatamente:` não entra no payload escrito;
- Conversar cria zero task e zero ação física;
- Executar objetivo usa `/api/tasks` e pipeline vigente;
- sucesso visual somente com evidência de GoalVerifier;
- telemetria ausente não é inventada;
- contexto de conversa sanitizado/versionado;
- Host/Origin e lease público protegidos;
- CI do candidato verde;
- Chromium exercita conversa e execução explícita;
- revisão Vinícius sem blocker;
- segurança Ricardo sem blocker;
- validação física com readback exato;
- auditoria Emily e gate Léo antes de integração.

## Estratégia de validação
TDD → CI por slice → Chromium → revisão de código → segurança → PRF → validação física → revalidação exata → Emily → Léo → integração se autorizada.
