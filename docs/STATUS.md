# STATUS

## Objetivo atual

Manter um operador digital local que recebe objetivos em linguagem natural e executa ações físicas em ciclo fechado, sem declarar `succeeded` até que o estado final seja comprovado por percepção independente e GoalVerifier.

## Base verificável atual

A `main` consolidada contém Home V4.1, Goal Runtime universal, FOCUS-RACE-001, providers Z.AI/Gemini/Cloudflare Workers AI, Policy Layer, lease/heartbeat, LeaseGuardedExecutor, FAILSAFE, Emergency Stop, Session Context pós-ACK, PM-DURABLE-JOURNAL-001, PM-LOCAL-VALIDATION-001, PM-LOCAL-VALIDATION-002 e PM-DURABLE-JOURNAL-RECOVERY-OBS-001.

O Durable Journal usa o mesmo SQLite da Central e protege a janela de replay com `task_id + action_key` e estados `prepared -> in_flight -> executed -> acknowledged`. Ação não repeat-safe em `in_flight` falha fechada; `executed` não substitui percepção independente nem GoalVerifier. Apenas `active_window` e `capture_screen` são repeat-safe nesta fase.

Comandos oficiais locais:

- `atualizar-robo`: atualização segura por fast-forward;
- `validar-robo`: compilação, pytest e requisitos Linux/X11/desktop/Chromium;
- `falha-robo`: fault injection local-only, one-shot.

Checkpoints físicos disponíveis: `after_prepare`, `after_in_flight`, `after_backend`, `after_executed`, `before_ack`, `after_ack`.

O host Linux/X11 foi validado em Python 3.12.3 com `399 passed, 1 warning`, compilação PASS, sessão X11 PASS, PyAutoGUI/Pillow/PyScreeze/xdotool/scrot PASS e Chromium Playwright PASS. Resultado observado: `RESULTADO: PRONTO PARA TESTE FÍSICO`.

## Matriz física atual

### Cenário normal — PASS

Objetivo `Abra o editor de texto e digite exatamente JOURNAL-SMOKE-NORMAL-001`: Xed abriu fisicamente, o texto apareceu uma única vez, readback foi confirmado, GoalVerifier marcou `SUCCEEDED` e a task terminou `succeeded`.

### `after_backend` — PASS fail-closed

Task `b0148f8c-4bfd-42f8-bb73-7ca243c68a8c`: após crash/reclaim voltou como tentativa 2, encontrou `open_app` em `in_flight`, gerou `ActionReplayBlocked`, registrou replay físico bloqueado e terminou `failed` sem nova emissão física autorizada.

### `after_executed` — PASS após correção

Primeiro ensaio revelou falha de observação do Xed já aberto após restart; isso originou o issue #14 e PM-DURABLE-JOURNAL-RECOVERY-OBS-001, integrado pelo PR #15. No reteste, task `6d07986b-5865-46bc-ac36-375b22c498e1` caiu após `executed`, permaneceu com Xed aberto, foi recuperada como tentativa 2 sem reemitir `open_app`, percebeu o Xed existente e terminou `succeeded`.

### `after_prepare` — PASS

Task `c376e052-8d72-4a5f-b768-e603672df252`: caiu na tentativa 1 depois de `prepared` e antes do backend; Xed não abriu. Após reclaim voltou como tentativa 2, executou `open_app` uma única vez e terminou `succeeded`.

### `after_in_flight` — PASS fail-closed

Task `8e993f29-273c-4024-9219-f4503ece4600`: caiu após persistir `in_flight` e antes do backend no checkpoint controlado; Xed não abriu. Após reclaim voltou como tentativa 2, encontrou estado ambíguo, registrou `ActionReplayBlocked`, não abriu Xed e terminou `failed`, que é o resultado correto de segurança.

### `before_ack` — PASS

Task `3b55952e-2e99-4d86-8d1b-f537111e5c12`: Xed abriu, o Robô chegou a resultado local de sucesso e caiu antes do aceite terminal da Central. Após expiração/reclaim voltou como tentativa 2, não houve nova abertura física observada e a task terminou `succeeded` após nova observação/GoalVerifier.

### `after_ack` — primeira metade PASS, restart final pendente

Task `39cbc255-ee3b-4c83-a34b-678883993a47`:

- `falha-robo armar after_ack` foi armado corretamente;
- Xed abriu fisicamente;
- a Central registrou a task como `succeeded` na tentativa 1 antes da queda;
- o Histórico mostra `Tarefa finalizada ... status=succeeded` e o Robô registrando `Tarefa executada ... resultado=sucesso`;
- após o checkpoint `after_ack`, Central permaneceu online e Robô ficou offline;
- em Tarefas, a mesma task já aparece `succeeded` na tentativa 1.

Primeira metade classificada como PASS. Falta religar somente o Robô e comprovar que a task continua terminal, não volta à fila, não ganha tentativa 2 e não reexecuta fisicamente `open_app`.

## PM-DURABLE-JOURNAL-RECOVERY-OBS-001

Concluída e integrada pelo PR #15. O recovery de `executed open_app` permanece zero-replay; quando necessário, a observação X11 passiva localiza janelas existentes sem focar, abrir, clicar ou digitar. Um XID recuperado é usado apenas como guarda efêmera para impedir teclado na janela errada. ExecutionReceipt continua insuficiente como prova de efeito; GoalVerifier continua autoridade final.

CI do head final do PR #15, run `31459234654`: PASS com `399 passed`, 1 warning e zero failures. CI pós-merge da `main`, run `31459378475`: PASS. Issue #14 encerrado como `completed` após reteste físico PASS.

## Migração, privacidade e ambiente local

`tasks` possui `journal_version` e `action_journal` é aditiva. Task legada nunca iniciada pode ser promovida; task legada já iniciada sem journal falha fechada por ambiguidade.

O journal não persiste texto digitado integral, screenshot ou URL completa. Receipts usam whitelist. Fault injection persiste somente identificadores técnicos sanitizados.

Existe um stash temporário com arquivos locais criado antes da atualização. Ele deve permanecer preservado até o encerramento da matriz física e então ser restaurado com conferência explícita.

## Situação

Cenário normal: PASS. `after_backend`: PASS fail-closed. `after_executed`: PASS. `after_prepare`: PASS. `after_in_flight`: PASS fail-closed. `before_ack`: PASS. `after_ack`: primeira metade PASS e restart final pendente. Depois desse último comprovante, consolidar a matriz completa e restaurar com segurança o stash local.