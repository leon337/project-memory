# STATUS

## Objetivo atual

Manter um operador digital local que recebe objetivos em linguagem natural e executa ações físicas em ciclo fechado, sem declarar `succeeded` até que o estado final seja comprovado por percepção independente e GoalVerifier.

## Estado verificável desta versão

A base consolidada contém Home V4.1, Goal Runtime universal, FOCUS-RACE-001, providers Z.AI/Gemini/Cloudflare Workers AI, Policy Layer, lease/heartbeat, LeaseGuardedExecutor, FAILSAFE, Emergency Stop, Session Context pós-ACK, PM-DURABLE-JOURNAL-001, PM-LOCAL-VALIDATION-001 e PM-LOCAL-VALIDATION-002.

### Durable Journal

A janela `ação física → crash → ACK ausente → reclaim → possível replay` é protegida pelo journal durável no SQLite da Central:

```text
task_id + action_key
        ↓
prepared
        ↓
in_flight
        ↓
executed
        ↓
acknowledged
```

- `prepared`: backend físico ainda não foi chamado;
- `in_flight`: backend pode ter produzido efeito; ação não repeat-safe fica fail-closed;
- `executed`: chamada física retornou e receipt mínimo foi persistido; não autoriza conclusão sem percepção independente;
- `acknowledged`: Central aceitou a task terminal e a row pode entrar em cleanup por retenção.

`action_key` é fingerprint task-scoped de `action + target`, sem target bruto persistido e sem contador implícito de retry. Apenas `active_window` e `capture_screen` são repeat-safe nesta fase.

### Operação e validação local

Comandos oficiais:

- `atualizar-robo`: atualização segura por fast-forward, recusando working tree suja ou commits locais não publicados;
- `validar-robo`: compilação, pytest e requisitos Linux/X11/desktop/Chromium;
- `falha-robo`: fault injection local-only, one-shot, sem endpoint de rede e sem simular a ação física.

Checkpoints atuais:

```text
after_prepare
after_in_flight
after_backend
after_executed
before_ack
after_ack
```

O primeiro `validar-robo` físico expôs teardown assíncrono do Playwright após PASS. PM-LOCAL-VALIDATION-002 corrigiu isso isolando o probe do Chromium em subprocesso. O CI do PR #13 passou com `396 passed`, e a repetição no mesmo host Linux/X11 com Python 3.12.3 terminou limpa em `RESULTADO: PRONTO PARA TESTE FÍSICO`.

## Validação física atual

### Cenário normal — PASS

Objetivo: `Abra o editor de texto e digite exatamente JOURNAL-SMOKE-NORMAL-001`.

Evidências: editor abriu fisicamente; texto apareceu exatamente uma vez; readback `Confirmado`; GoalVerifier `SUCCEEDED`; task `succeeded`; logs sem duplicidade visível.

### Crash `after_backend` — PASS

Cenário: `Abra o editor de texto` com `falha-robo armar after_backend`.

Após restart/reclaim, a mesma task `b0148f8c-4bfd-42f8-bb73-7ca243c68a8c` voltou como tentativa 2, encontrou `open_app` em `in_flight`, gerou `ActionReplayBlocked`, registrou `Replay físico bloqueado ... state=in_flight` e terminou `failed` fail-closed sem nova emissão autorizada de `open_app`.

### Crash `after_executed` — anti-replay PASS, recovery end-to-end FAIL

Cenário: `Abra o editor de texto` com `falha-robo armar after_executed`.

Primeira metade observada:

- task `3225f2ef-862e-4fd3-8a63-97ca7b091bd2` abriu Xed fisicamente;
- fault injection encerrou o Robô depois de o journal persistir a ação como `executed`;
- Central permaneceu online e a task ficou `running` até reclaim.

Após restart/reclaim como tentativa 2:

- não apareceu `ActionReplayBlocked` para `open_app`, coerente com recovery de `executed`;
- não foi observada nova abertura física do editor;
- o editor permaneceu aberto;
- a task terminou `failed` com `GoalExecutionFailed: RuntimeError: Xed abriu, mas a capacidade não foi observada`.

Conclusão: a propriedade de **zero replay físico** para `executed` passou neste cenário, mas o recovery completo falhou porque a percepção/verificação não reconheceu de forma suficiente o aplicativo já aberto. Essa lacuna está registrada no issue #14 `PM-DURABLE-JOURNAL-RECOVERY-OBS-001`.

## Migração, privacidade e compatibilidade

`tasks` possui `journal_version` e `action_journal` é aditiva. Task legada nunca iniciada (`queued`, `attempts=0`) pode ser promovida; task legada já iniciada sem journal falha fechada por ambiguidade.

O journal não persiste texto digitado integral, screenshot ou URL completa. Receipts usam whitelist no agente e na Central. Fault injection persiste apenas checkpoint, PID e identificadores técnicos sanitizados.

## Situação

Máquina local validada. Cenário físico normal: PASS. `after_backend`: PASS. `after_executed`: anti-replay PASS, mas recovery/verificação end-to-end FAIL. A bateria de crashes está pausada até corrigir o issue #14 e repetir `after_executed`; não avançar para os checkpoints restantes antes desse reteste.