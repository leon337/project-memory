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

Após a publicação de PM-DURABLE-JOURNAL-RECOVERY-OBS-001, o host Linux/X11 foi atualizado novamente e o `validar-robo` terminou limpo em Python 3.12.3: repositório PASS, working tree limpa, branch `main`, compilação PASS, `399 passed, 1 warning`, desktop habilitado PASS, sessão X11 PASS, PyAutoGUI/Pillow/PyScreeze/xdotool/scrot PASS e Chromium Playwright PASS. Resultado final observado: `RESULTADO: PRONTO PARA TESTE FÍSICO`.

## Validação física atual

### Cenário normal — PASS

Objetivo: `Abra o editor de texto e digite exatamente JOURNAL-SMOKE-NORMAL-001`.

Evidências: editor abriu fisicamente; texto apareceu exatamente uma vez; readback `Confirmado`; GoalVerifier `SUCCEEDED`; task `succeeded`; logs sem duplicidade visível.

### Crash `after_backend` — PASS

Cenário: `Abra o editor de texto` com `falha-robo armar after_backend`.

Após restart/reclaim, a mesma task `b0148f8c-4bfd-42f8-bb73-7ca243c68a8c` voltou como tentativa 2, encontrou `open_app` em `in_flight`, gerou `ActionReplayBlocked`, registrou `Replay físico bloqueado ... state=in_flight` e terminou `failed` fail-closed sem nova emissão autorizada de `open_app`.

### Crash `after_executed` — anti-replay PASS, recovery end-to-end FAIL no primeiro ensaio

Cenário: `Abra o editor de texto` com `falha-robo armar after_executed`.

No primeiro ensaio físico, a task `3225f2ef-862e-4fd3-8a63-97ca7b091bd2` abriu Xed e caiu depois de persistir `executed`. No reclaim como tentativa 2 não houve nova abertura física, mas a task terminou `failed` com `GoalExecutionFailed: RuntimeError: Xed abriu, mas a capacidade não foi observada`, apesar de o Xed continuar aberto. O Painel/Brave havia se tornado a janela ativa durante o restart.

## PM-DURABLE-JOURNAL-RECOVERY-OBS-001 — publicada; reteste físico pendente

O issue #14 registra a falha acima e permanece aberto até prova física da correção.

A correção foi integrada pelo PR #15 na `main` como commit `5da8df2a199747a649c9ffa4ab53ff85152f8996`.

Implementação publicada:

- recovery de `executed open_app` continua zero-replay; o backend físico não é chamado novamente;
- o receipt recuperado apenas arma um marcador efêmero para exigir nova observação independente;
- a observação normal da janela ativa continua sendo tentada primeiro;
- se ela falhar nesse recovery específico, `recovery_observation.py` enumera passivamente janelas X11 já gerenciadas via `_NET_CLIENT_LIST_STACKING`/`_NET_CLIENT_LIST`, compara `WM_CLASS` e consulta XID/título/PID/processo quando disponíveis;
- a observação passiva não abre, ativa, levanta ou foca janela, não clica e não digita;
- XIDs são normalizados para comparação consistente com `xdotool`;
- quando uma janela recuperada é reconhecida, seu XID fica apenas como guarda efêmera: `type_text`/`press_key` falham fechados se outra janela estiver ativa, evitando teclado acidental no Painel/Brave;
- EvidenceRecord e GoalVerifier continuam responsáveis pela conclusão; ExecutionReceipt continua insuficiente como prova de efeito.

Regressões adicionadas cobrem recovery `executed open_app` sem replay, localização passiva de Xed inativo enquanto outra janela está ativa e recusa de teclado quando o foco não está na janela recuperada.

CI do head final do PR #15, run `31459234654`: PASS com `399 passed`, 1 warning de depreciação do stack de teste e zero failures. CI pós-merge da `main`, run `31459378475`: PASS em todas as etapas de instalação, Playwright, compilação e testes.

Ainda não existe PASS físico da correção publicada; ele só poderá ser declarado depois de repetir exatamente o smoke `after_executed` no host agora revalidado.

## Migração, privacidade e compatibilidade

`tasks` possui `journal_version` e `action_journal` é aditiva. Task legada nunca iniciada (`queued`, `attempts=0`) pode ser promovida; task legada já iniciada sem journal falha fechada por ambiguidade.

O journal não persiste texto digitado integral, screenshot ou URL completa. Receipts usam whitelist no agente e na Central. Fault injection persiste apenas checkpoint, PID e identificadores técnicos sanitizados. A observação de recovery consulta metadados atuais de janelas/processos X11 necessários à verificação e não persiste objetivo ou target bruto.

## Situação

Host atualizado e novamente validado após a correção, com `399 passed` e `RESULTADO: PRONTO PARA TESTE FÍSICO`. Cenário físico normal: PASS. `after_backend`: PASS. Primeiro `after_executed`: anti-replay PASS, recovery/verificação FAIL. A correção correspondente está publicada e o host está pronto; o próximo passo obrigatório é repetir exatamente o `after_executed`. A bateria de crashes permanece pausada até esse reteste real.