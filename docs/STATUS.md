# STATUS

## Objetivo atual

Manter um operador digital local que recebe objetivos em linguagem natural e executa ações físicas em ciclo fechado, sem declarar `succeeded` até que o estado final seja comprovado por percepção independente e GoalVerifier.

A próxima direção estratégica já foi escolhida: evoluir o produto para um **Operador Digital Autônomo Multimodal**, capaz de transformar objetivos em linguagem natural em trabalho real no computador e em serviços digitais. A fase de implementação ainda não começou; o escopo e a arquitetura serão debatidos e planejados com o MCF antes de qualquer alteração de código.

## Base verificável atual

A `main` consolidada contém Home V4.1, Goal Runtime universal, FOCUS-RACE-001, providers Z.AI/Gemini/Cloudflare Workers AI, Policy Layer, lease/heartbeat, LeaseGuardedExecutor, FAILSAFE, Emergency Stop, Session Context pós-ACK, PM-DURABLE-JOURNAL-001, PM-LOCAL-VALIDATION-001, PM-LOCAL-VALIDATION-002 e PM-DURABLE-JOURNAL-RECOVERY-OBS-001.

O Durable Journal usa o SQLite da Central e protege a janela de replay com `task_id + action_key` e estados `prepared -> in_flight -> executed -> acknowledged`. Ação não repeat-safe em `in_flight` falha fechada; `executed` não substitui percepção independente nem GoalVerifier. Apenas `active_window` e `capture_screen` são repeat-safe nesta fase.

Comandos oficiais locais:

- `atualizar-robo`: atualização segura por fast-forward;
- `validar-robo`: compilação, pytest e requisitos Linux/X11/desktop/Chromium;
- `falha-robo`: fault injection local-only, one-shot.

Checkpoints físicos: `after_prepare`, `after_in_flight`, `after_backend`, `after_executed`, `before_ack`, `after_ack`.

O host Linux/X11 foi validado em Python 3.12.3 com `399 passed, 1 warning`, compilação PASS, sessão X11 PASS, PyAutoGUI/Pillow/PyScreeze/xdotool/scrot PASS e Chromium Playwright PASS. Resultado observado: `RESULTADO: PRONTO PARA TESTE FÍSICO`.

## Matriz física concluída

### Cenário normal — PASS

Task `3e5e77ac-deda-4ac1-abf2-9188532efbc1`: Xed abriu fisicamente, `JOURNAL-SMOKE-NORMAL-001` apareceu uma única vez, readback foi confirmado, GoalVerifier marcou `SUCCEEDED` e a task terminou `succeeded`.

### `after_backend` — PASS fail-closed

Task `b0148f8c-4bfd-42f8-bb73-7ca243c68a8c`: após crash/reclaim voltou como tentativa 2, encontrou `open_app` em `in_flight`, gerou `ActionReplayBlocked`, registrou replay físico bloqueado e terminou `failed` sem nova emissão física autorizada.

### `after_executed` — PASS após correção

O primeiro ensaio revelou falha de observação do Xed já aberto após restart; isso originou o issue #14 e PM-DURABLE-JOURNAL-RECOVERY-OBS-001, integrado pelo PR #15. No reteste, task `6d07986b-5865-46bc-ac36-375b22c498e1` caiu após `executed`, permaneceu com Xed aberto, foi recuperada como tentativa 2 sem reemitir `open_app`, percebeu o Xed existente e terminou `succeeded`.

### `after_prepare` — PASS

Task `c376e052-8d72-4a5f-b768-e603672df252`: caiu na tentativa 1 depois de `prepared` e antes do backend; Xed não abriu. Após reclaim voltou como tentativa 2, executou `open_app` uma única vez e terminou `succeeded`.

### `after_in_flight` — PASS fail-closed

Task `8e993f29-273c-4024-9219-f4503ece4600`: caiu após persistir `in_flight` e antes do backend no checkpoint controlado; Xed não abriu. Após reclaim voltou como tentativa 2, encontrou estado ambíguo, registrou `ActionReplayBlocked`, não abriu Xed e terminou `failed`, que é o resultado correto de segurança.

### `before_ack` — PASS

Task `3b55952e-2e99-4d86-8d1b-f537111e5c12`: Xed abriu, o Robô chegou a resultado local de sucesso e caiu antes do aceite terminal da Central. Após expiração/reclaim voltou como tentativa 2, não houve nova abertura física observada e a task terminou `succeeded` após nova observação/GoalVerifier.

### `after_ack` — PASS

Task `39cbc255-ee3b-4c83-a34b-678883993a47`:

- Xed abriu fisicamente;
- a Central registrou `succeeded` na tentativa 1 antes do crash;
- o checkpoint `after_ack` encerrou somente o Robô depois do aceite terminal;
- após religar o Robô, a task permaneceu `succeeded` na tentativa 1;
- não voltou a `queued`/`running`, não ganhou tentativa 2 e não houve nova entrega/reclaim dessa task nos logs observados;
- não foi observada nova abertura física do Xed.

Conclusão: task terminal após ACK permanece terminal e não reexecuta efeito físico.

## Resultado da fase PM-DURABLE-JOURNAL-001

A matriz física está completa no host Linux/X11 real: cenário normal, `after_prepare`, `after_in_flight`, `after_backend`, `after_executed`, `before_ack` e `after_ack` foram executados. Os cenários ambíguos `after_backend`/`after_in_flight` passaram por fail-closed; os demais comprovaram recovery sem replay físico cego.

ExecutionReceipt continua insuficiente como prova de efeito. Percepção independente, EvidenceRecord e GoalVerifier permanecem a cadeia autorizada para conclusão. A arquitetura de lease/journal preservou a identidade da ação entre tentativas e impediu que retries/reclaims fabricassem uma segunda emissão não autorizada.

A matriz consolidada também está registrada em `artifacts/phases/PHASE-01-PM-DURABLE-JOURNAL-001/CRASH-RECOVERY-MATRIX.md`.

## PM-DURABLE-JOURNAL-RECOVERY-OBS-001

Concluída e integrada pelo PR #15. O recovery de `executed open_app` permanece zero-replay; quando necessário, a observação X11 passiva localiza janelas existentes sem focar, abrir, clicar ou digitar. Um XID recuperado é usado apenas como guarda efêmera para impedir teclado na janela errada. Issue #14 foi encerrado após reteste físico PASS.

CI do head final do PR #15, run `31459234654`: PASS com `399 passed`, 1 warning e zero failures. CI pós-merge da `main`, run `31459378475`: PASS.

## Migração, privacidade e ambiente local

`tasks` possui `journal_version` e `action_journal` é aditiva. Task legada nunca iniciada pode ser promovida; task legada já iniciada sem journal falha fechada por ambiguidade.

O journal não persiste texto digitado integral, screenshot ou URL completa. Receipts usam whitelist. Fault injection persiste somente identificadores técnicos sanitizados.

A restauração do ambiente local foi concluída em 2026-08-11: a `main` local foi sincronizada por `atualizar-robo`, o stash temporário `backup-local-antes-atualizacao-2026-08-10` foi aplicado, os arquivos locais reapareceram como não rastreados (`??`), o stash permaneceu disponível durante a conferência e só então foi removido com `git stash drop`. Após o drop, `git stash list` ficou sem esse backup e os arquivos locais continuaram presentes. Não foram observados marcadores de conflito na saída conferida.

O working tree local volta a conter deliberadamente esses arquivos locais não rastreados; isso é estado esperado do host e deve ser tratado antes de uma futura execução de `atualizar-robo`, que exige working tree limpa.

## Próxima direção estratégica aprovada

A decisão D-032 oficializa como direção de produto a evolução para um **Operador Digital Autônomo Multimodal**. O alvo é reduzir o trabalho operacional manual entre intenção e execução: receber objetivos em linguagem natural, decompor tarefas e atuar em projetos locais, Git/GitHub, navegador e serviços como Cloudflare, Vercel e Render usando a melhor interface disponível.

O nome de trabalho é `PM-UNIVERSAL-OPERATOR-001 — Natural Language → Real Computer Work`.

Voz bidirecional, contexto conversacional operacional, gestão segura de credenciais e ponte ChatGPT → Robô são frentes candidatas para o debate, não arquitetura fechada. Nenhuma implementação dessa nova fase foi iniciada.

## RC 3.5 pré-quarta rodada — concluída como proposta, aguardando aprovação

Foi executada uma crítica de arquitetura, engenharia e UI/UX sobre a arquitetura V3 antes de congelar contratos.

Principais conclusões propostas, ainda não incorporadas a `ARCHITECTURE.md` ou `DECISIONS.md`:

- evitar um `Durable Execution Manifest` como máquina de estados paralela ao journal; a alternativa preferida para a quarta rodada é evoluir o Durable Action Journal para uma identidade semântica de efeito v2 e persistir apenas um fingerprint mínimo do contrato de execução no nível da task;
- `effect_key` deve ser produzido deterministicamente pelo runtime, nunca pelo provider; rota e efeito continuam identidades distintas;
- a rota escolhida deve ser fixada atomicamente antes da entrada no backend e não pode trocar cegamente depois de estado ambíguo;
- o Route Resolver deve ser determinístico e baseado em metadados de disponibilidade, autenticação, policy, replay/recovery e verificabilidade, não em ranking livre da IA;
- Credential Broker deve entregar apenas credencial/ambiente mínimo ao adapter, sem segredo em prompt, argv, log, journal, contexto ou resultado público;
- adapters devem ser tipados e pequenos; não criar uma interface universal excessiva antes de o slice Git/GitHub provar quais operações são realmente comuns;
- toda escrita externa deve possuir recovery de três vias (`effect_present`, `effect_absent`, `ambiguous`) e observação posterior independente do receipt;
- conteúdo vindo de web, GitHub, arquivos, terminal e ferramentas externas é dado não confiável e não pode adquirir autoridade de instrução sobre o runtime;
- a UI do Operador Universal deve mostrar progresso operacional simples e verificável, mantendo detalhes técnicos em camada secundária;
- logs não podem ser usados como fonte de estado visual. Para `planning`, `executing`, `verifying` e `recovering`, a quarta rodada deve definir um snapshot/contrato estruturado de telemetria proveniente do Goal Runtime/Journal e publicado pela Central;
- `blocked` não deve ser apresentado como estado resumível enquanto o backend não possuir esse estado real. Falhas fail-closed devem aparecer como falha segura com código/motivo real;
- cada componente da UI deve ter fonte real no runtime; nenhum indicador meramente ilustrativo deve entrar no Painel.

A RC também propôs manter a Home V4.1 como fundação, em vez de redesenhar o produto do zero. A candidata de UX é uma superfície principal simples com objetivo atual, progresso por etapas, distinção visual entre executado e comprovado, recuperação/falha segura e um drawer/painel de detalhes técnicos para capability, rota, journal, lease e evidências sanitizadas.

Nenhum código da `PM-UNIVERSAL-OPERATOR-001` foi implementado e nenhuma dessas propostas está aprovada como arquitetura vigente.

## Situação

PM-DURABLE-JOURNAL-001 está fisicamente validada no host Linux/X11 para toda a matriz planejada, e o ambiente local foi restaurado sem perda visível dos arquivos preservados. Nenhum checkpoint físico do Durable Journal permanece pendente.

A direção de produto está definida e a RC 3.5 foi concluída como proposta. O próximo passo é aprovar, modificar ou rejeitar suas conclusões antes da quarta rodada. Só depois disso a arquitetura aprovada deve ser registrada em `ARCHITECTURE.md`/`DECISIONS.md` e convertida em contrato implementável.