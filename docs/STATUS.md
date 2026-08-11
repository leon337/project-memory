# STATUS

## Objetivo atual

Manter um operador digital local que recebe objetivos em linguagem natural e executa ações físicas em ciclo fechado, sem declarar `succeeded` até que o estado final seja comprovado por percepção independente e GoalVerifier.

## Estado verificável desta versão

A base consolidada contém Home V4.1, Goal Runtime universal, FOCUS-RACE-001, providers Z.AI/Gemini/Cloudflare Workers AI, Policy Layer, lease/heartbeat, LeaseGuardedExecutor, FAILSAFE, Emergency Stop, Session Context pós-ACK, PM-DURABLE-JOURNAL-001, PM-LOCAL-VALIDATION-001, PM-LOCAL-VALIDATION-002 e PM-DURABLE-JOURNAL-RECOVERY-OBS-001.

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

Checkpoints atuais: `after_prepare`, `after_in_flight`, `after_backend`, `after_executed`, `before_ack`, `after_ack`.

Após a publicação de PM-DURABLE-JOURNAL-RECOVERY-OBS-001, o host Linux/X11 foi atualizado e o `validar-robo` terminou limpo em Python 3.12.3: repositório PASS, working tree limpa, branch `main`, compilação PASS, `399 passed, 1 warning`, desktop habilitado PASS, sessão X11 PASS, PyAutoGUI/Pillow/PyScreeze/xdotool/scrot PASS e Chromium Playwright PASS. Resultado final observado: `RESULTADO: PRONTO PARA TESTE FÍSICO`.

## Validação física atual

### Cenário normal — PASS

Objetivo: `Abra o editor de texto e digite exatamente JOURNAL-SMOKE-NORMAL-001`.

Evidências: editor abriu fisicamente; texto apareceu exatamente uma vez; readback `Confirmado`; GoalVerifier `SUCCEEDED`; task `succeeded`; logs sem duplicidade visível.

### Crash `after_backend` — PASS

Cenário: `Abra o editor de texto` com `falha-robo armar after_backend`.

Após restart/reclaim, a mesma task `b0148f8c-4bfd-42f8-bb73-7ca243c68a8c` voltou como tentativa 2, encontrou `open_app` em `in_flight`, gerou `ActionReplayBlocked`, registrou `Replay físico bloqueado ... state=in_flight` e terminou `failed` fail-closed sem nova emissão autorizada de `open_app`.

### Crash `after_executed` — PASS após correção

Primeiro ensaio físico: task `3225f2ef-862e-4fd3-8a63-97ca7b091bd2` preservou zero replay, mas falhou ao observar o Xed já aberto após restart porque Painel/Brave estava ativo. Isso originou o issue #14 e a correção PM-DURABLE-JOURNAL-RECOVERY-OBS-001.

Reteste físico após o PR #15:

- task `6d07986b-5865-46bc-ac36-375b22c498e1` executou `Abra o editor de texto`;
- o fault injection encerrou o Robô após o journal persistir `executed`;
- o Xed permaneceu aberto;
- após expiração do lease, a mesma task foi recuperada como tentativa 2;
- não foi observada nova abertura física do editor;
- a percepção independente reconheceu o Xed já existente no recovery;
- a task terminou `succeeded` na tentativa 2;
- logs registraram `Tarefa recebida`, `Tarefa executada ... resultado=sucesso` e `Resultado enviado ... status=succeeded` para a mesma task recuperada.

Conclusão: `after_executed` passa end-to-end no host Linux/X11 real, preservando zero replay de `open_app`, nova percepção independente e GoalVerifier como autoridade final.

### Crash `after_prepare` — PASS

Cenário: `Abra o editor de texto` com `falha-robo armar after_prepare`.

- task `c376e052-8d72-4a5f-b768-e603672df252` caiu na tentativa 1 depois de persistir `prepared` e antes de chamar o backend físico;
- antes do crash o Xed não abriu, confirmando ausência de efeito físico;
- Central permaneceu online e Robô ficou offline;
- após religar o Robô e ocorrer reclaim, a mesma task voltou como tentativa 2;
- nessa segunda tentativa o Xed abriu fisicamente uma única vez;
- a task terminou `succeeded`;
- logs registraram `Tarefa recebida`, `Tarefa executada ... resultado=sucesso` e `Resultado enviado ... status=succeeded` para a mesma task recuperada.

Conclusão: estado `prepared` é recuperável com segurança porque o backend físico ainda não havia sido chamado; a ação pode ser executada uma vez após reclaim e continuar sujeita à percepção independente e GoalVerifier.

### Crash `after_in_flight` — PASS

Cenário: `Abra o editor de texto` com `falha-robo armar after_in_flight`.

- task `8e993f29-273c-4024-9219-f4503ece4600` foi criada, entregue e recebida na tentativa 1;
- o Robô caiu depois da transição durável para `in_flight` e antes da chamada física ao backend no checkpoint controlado;
- antes do crash o Xed não abriu;
- Central permaneceu online e Robô ficou offline;
- após religar o Robô e expirar o lease, a mesma task voltou como tentativa 2;
- o Journal encontrou `open_app` em estado `in_flight`;
- o Robô registrou `Replay físico bloqueado ... state=in_flight` e não abriu o Xed;
- a task terminou `failed` fail-closed, que é o resultado correto de segurança neste estado ambíguo.

Conclusão: `in_flight` não é tratado como autorização para repetir uma ação não repeat-safe. O recovery bloqueia replay físico quando não há prova suficiente de que o efeito externo ocorreu ou não ocorreu.

### Crash `before_ack` — PASS

Cenário: `Abra o editor de texto` com `falha-robo armar before_ack`.

- task `3b55952e-2e99-4d86-8d1b-f537111e5c12` foi criada, entregue e recebida na tentativa 1;
- o Xed abriu fisicamente;
- o Robô registrou localmente `Tarefa executada ... resultado=sucesso` e caiu antes do aceite terminal da Central;
- Central permaneceu online, Robô ficou offline e a task permaneceu `running` na tentativa 1;
- após religar o Robô e expirar o lease, a mesma task foi entregue novamente como tentativa 2;
- o recovery concluiu a mesma task sem evidência de nova abertura física do editor;
- logs da tentativa 2 registraram `Tarefa recebida`, `Tarefa executada ... resultado=sucesso` e `Resultado enviado ... status=succeeded`;
- a Central registrou a task como `succeeded` na tentativa 2.

Conclusão: a queda depois da ação/verificação local, mas antes do ACK terminal da Central, não força replay físico cego; o estado executado é recuperado e a task pode concluir após nova observação/GoalVerifier.

## PM-DURABLE-JOURNAL-RECOVERY-OBS-001 — concluída

A correção foi integrada pelo PR #15 na `main` como commit `5da8df2a199747a649c9ffa4ab53ff85152f8996`.

Implementação publicada:

- recovery de `executed open_app` continua zero-replay; o backend físico não é chamado novamente;
- o receipt recuperado apenas arma um marcador efêmero para exigir nova observação independente;
- a observação normal da janela ativa continua sendo tentada primeiro;
- se ela falhar nesse recovery específico, `recovery_observation.py` enumera passivamente janelas X11 já gerenciadas via `_NET_CLIENT_LIST_STACKING`/`_NET_CLIENT_LIST`, compara `WM_CLASS` e consulta XID/título/PID/processo quando disponíveis;
- a observação passiva não abre, ativa, levanta ou foca janela, não clica e não digita;
- XIDs são normalizados para comparação consistente com `xdotool`;
- quando uma janela recuperada é reconhecida, seu XID fica apenas como guarda efêmera: `type_text`/`press_key` falham fechados se outra janela estiver ativa;
- EvidenceRecord e GoalVerifier continuam responsáveis pela conclusão; ExecutionReceipt continua insuficiente como prova de efeito.

Regressões adicionadas cobrem recovery `executed open_app` sem replay, localização passiva de Xed inativo enquanto outra janela está ativa e recusa de teclado quando o foco não está na janela recuperada.

CI do head final do PR #15, run `31459234654`: PASS com `399 passed`, 1 warning e zero failures. CI pós-merge da `main`, run `31459378475`: PASS em todas as etapas. O reteste físico posterior também passou. Issue #14 encerrado como `completed`.

## Migração, privacidade e compatibilidade

`tasks` possui `journal_version` e `action_journal` é aditiva. Task legada nunca iniciada (`queued`, `attempts=0`) pode ser promovida; task legada já iniciada sem journal falha fechada por ambiguidade.

O journal não persiste texto digitado integral, screenshot ou URL completa. Receipts usam whitelist no agente e na Central. Fault injection persiste apenas checkpoint, PID e identificadores técnicos sanitizados. A observação de recovery consulta metadados atuais de janelas/processos X11 necessários à verificação e não persiste objetivo ou target bruto.

## Situação

Host Linux/X11 validado com `399 passed`. Cenário físico normal: PASS. `after_backend`: PASS. `after_executed`: PASS end-to-end após correção do issue #14. `after_prepare`: PASS end-to-end. `after_in_flight`: PASS fail-closed. `before_ack`: PASS end-to-end. Resta somente o checkpoint físico `after_ack`; depois consolidar a matriz e restaurar com segurança o stash local.