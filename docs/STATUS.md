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

### Crash `after_executed` — anti-replay PASS, recovery end-to-end FAIL no primeiro ensaio

Cenário: `Abra o editor de texto` com `falha-robo armar after_executed`.

Primeiro ensaio físico:

- task `3225f2ef-862e-4fd3-8a63-97ca7b091bd2` abriu Xed fisicamente;
- fault injection encerrou o Robô depois de o journal persistir a ação como `executed`;
- após restart/reclaim como tentativa 2 não foi observada nova abertura física do editor;
- o editor permaneceu aberto;
- a task terminou `failed` com `GoalExecutionFailed: RuntimeError: Xed abriu, mas a capacidade não foi observada`.

Conclusão do ensaio: zero replay físico para `executed` passou, mas a percepção independente pós-recovery não reconheceu o Xed já aberto porque o Painel/Brave havia se tornado a janela ativa durante o restart.

## PM-DURABLE-JOURNAL-RECOVERY-OBS-001 — correção implementada, reteste físico pendente

Issue #14 documenta a falha do primeiro `after_executed`. A correção está no PR #15.

Implementação:

- `LeaseGuardedExecutor` mantém o comportamento de zero-replay quando encontra `open_app` em estado `executed`;
- o receipt recuperado apenas arma um marcador efêmero para a próxima observação independente de aplicação;
- a observação normal da janela ativa continua sendo tentada primeiro;
- se ela falhar nesse recovery específico, `recovery_observation.py` enumera passivamente janelas X11 já gerenciadas por `_NET_CLIENT_LIST_STACKING`/`_NET_CLIENT_LIST` e compara `WM_CLASS` com a identidade esperada;
- a busca passiva não abre, ativa, levanta ou foca janela, não clica e não digita;
- se uma janela existente for observada, EvidenceRecord/GoalVerifier continuam decidindo a conclusão. O receipt não vira prova de efeito.

Regressões adicionadas:

- recovery de `executed open_app` com Painel/Brave ativo e Xed existente deve concluir sem qualquer nova chamada física a `open_app`;
- enumeração passiva deve ignorar a janela ativa não correspondente e localizar um Xed inativo correspondente.

CI do head de implementação `51f042642ae7e00931b7f1a74dbd14bfdcc75d2f`, run `31458732207`: PASS, `398 passed`, 1 warning de depreciação do stack de teste, zero failures.

A documentação arquitetural foi atualizada no mesmo PR; commits documentais posteriores ainda precisam manter CI verde antes do merge.

## Migração, privacidade e compatibilidade

`tasks` possui `journal_version` e `action_journal` é aditiva. Task legada nunca iniciada (`queued`, `attempts=0`) pode ser promovida; task legada já iniciada sem journal falha fechada por ambiguidade.

O journal não persiste texto digitado integral, screenshot ou URL completa. Receipts usam whitelist no agente e na Central. Fault injection persiste apenas checkpoint, PID e identificadores técnicos sanitizados.

A nova observação de recovery consulta apenas metadados atuais de janelas/processos X11 necessários à verificação e não persiste o objetivo ou target bruto.

## Situação

Máquina local validada. Cenário físico normal: PASS. `after_backend`: PASS. Primeiro `after_executed`: anti-replay PASS, recovery/verificação FAIL. A correção do issue #14 está implementada no PR #15 e passou sua regressão automatizada no head de código. Ainda não existe PASS físico da correção: depois do merge e atualização do host, é obrigatório repetir exatamente `after_executed`. A bateria permanece pausada até esse reteste real.