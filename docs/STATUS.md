# STATUS

## Objetivo atual

Manter um operador digital local que recebe objetivos em linguagem natural e executa ações físicas em ciclo fechado, sem declarar `succeeded` até que o estado final seja comprovado por percepção independente e GoalVerifier.

## Estado verificável desta versão

A base consolidada contém:

- Home V4.1;
- Goal Runtime universal;
- FOCUS-RACE-001 / estabilidade de foco Linux/X11;
- providers Z.AI, Gemini e Cloudflare Workers AI;
- Policy Layer, lease/heartbeat, LeaseGuardedExecutor, FAILSAFE e Emergency Stop;
- Session Context commitado somente depois do ACK da Central;
- PM-DURABLE-JOURNAL-001 integrado na `main` pelo PR #9;
- PM-LOCAL-VALIDATION-001 integrado na `main` pelo PR #11;
- PM-LOCAL-VALIDATION-002 integrado na `main` pelo PR #13 para corrigir o teardown do probe Playwright observado no primeiro `validar-robo` físico.

## PM-DURABLE-JOURNAL-001

A janela residual `ação física → crash → ACK ausente → reclaim → possível replay` recebeu proteção durável no mesmo SQLite da Central.

Contrato atual:

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

Semântica:

- `prepared`: backend físico ainda não foi chamado;
- `in_flight`: backend pode ter produzido efeito; ação não repeat-safe fica fail-closed;
- `executed`: chamada física retornou e um receipt mínimo foi persistido; a ação não é reemitida, mas o GoalVerifier ainda exige percepção independente;
- `acknowledged`: Central aceitou a task terminal; row passa a ser elegível a cleanup por retenção.

`action_key` é um fingerprint task-scoped de `action + target`. O target bruto não é persistido e não existe contador implícito de retry que permita criar uma segunda identidade para a mesma ação+target.

Apenas `active_window` e `capture_screen` são tratadas como repeat-safe nesta fase. Demais ações externas/físicas permanecem conservadoras.

## PM-LOCAL-VALIDATION-001

A rotina repetitiva de manutenção local foi convertida em comandos oficiais:

- `atualizar-robo`: valida o repositório, recusa working tree suja ou commits locais não publicados, faz apenas fast-forward de `main`, sincroniza `.venv`, dependências e Chromium;
- `validar-robo`: compila `src/tests`, executa a suíte `pytest` e verifica Python, X11, desktop, PyAutoGUI/Pillow/PyScreeze, `xdotool`, `scrot` e Chromium;
- `falha-robo`: arma localmente um crash one-shot em checkpoint conhecido, sem endpoint de rede e sem simular a ação física.

Checkpoints atuais do fault injection:

```text
after_prepare
after_in_flight
after_backend
after_executed
before_ack
after_ack
```

O armamento fica em `runtime/`, é desarmado por padrão, é consumido atomicamente antes do encerramento proposital e persiste somente identificadores técnicos sanitizados. O processo encerrado é o Robô local; Central/Painel não recebem uma API para armar fault injection.

Ações físicas, SQLite, journal, lease, reclaim e restart permanecem reais no smoke físico; apenas o instante do crash é controlado.

As melhorias posteriores do processo de testes foram planejadas e publicadas em `docs/VALIDATION-ROADMAP.md`. A implementação atual não inclui ainda `teste-robo`, integração de validação no Painel, bundle automático de evidências, histórico ou matriz de ambientes.

## PM-LOCAL-VALIDATION-002

O primeiro `validar-robo` executado no host Linux/X11 real chegou a imprimir todos os checks como PASS e `395 passed`, mas depois de `RESULTADO: PRONTO PARA TESTE FÍSICO` o processo emitiu:

```text
Task was destroyed but it is pending!
TargetClosedError(...)
```

Esse resultado não foi aceito como validação limpa e o smoke físico foi interrompido antes de qualquer ação do Robô.

A origem ficou localizada no probe usado apenas para consultar `playwright.chromium.executable_path`: o validador iniciava `sync_playwright()` no próprio processo. A correção do PR #13 move esse probe para um subprocesso curto usando o Python da `.venv`, captura stdout/stderr do driver e devolve ao processo principal apenas o resultado do path.

O CI do PR #13, run `31448585330`, passou integralmente com `396 passed`, zero failures. O PR foi integrado por squash na `main` como commit `4ff470250bc7868f41846488fcfd1c1b4be24fd3`; issue #12 foi encerrado como `completed`.

A repetição no mesmo host físico Linux/X11 com Python 3.12.3 passou limpa após `atualizar-robo && validar-robo`: repositório, working tree, branch, Python, compilação, `396 passed`, desktop, X11, PyAutoGUI, Pillow, PyScreeze, `xdotool`, `scrot` e Chromium ficaram PASS, terminando em `RESULTADO: PRONTO PARA TESTE FÍSICO` sem reaparecer `Task was destroyed`, `TargetClosedError` ou outra exceção visível após o resultado.

## Migração e compatibilidade

`tasks` recebe `journal_version` e `action_journal` é criada de forma aditiva.

- task legada nunca iniciada (`queued`, `attempts=0`) pode ser claimada e promovida para journal v1;
- task legada já iniciada sem journal é ambígua e recebe `failed` fail-closed, em vez de ser reclamada cegamente.

O fault injection adiciona apenas arquivos locais ignorados pelo Git; não altera o schema SQLite nem a autoridade de conclusão.

## Privacidade

O journal não persiste texto integral digitado, screenshot ou URL completa. Receipts passam por whitelist no agente e novamente na Central. O último evento de fault injection persiste apenas checkpoint, PID e identificadores técnicos permitidos (`task_id`, `action_key`, `action_name`, status). Credenciais continuam fora de Git/logs/prompts.

## Validação

PM-DURABLE-JOURNAL-001 teve CI verde antes do merge do PR #9.

Para PM-LOCAL-VALIDATION-001:

- a primeira execução de CI, run `31447120929`, encontrou uma regressão real de compatibilidade: 5 testes antigos falharam porque test doubles de `LocalAgentSettings` não possuíam os novos paths de fault injection;
- a inicialização foi corrigida com defaults locais compatíveis;
- o CI final do PR, run `31447526239`, passou com `395 passed`;
- o PR #11 foi integrado por squash na `main` como `e3b2a7ed31d4c18985bd2423169c06b42cf90a7b`;
- o CI pós-merge run `31447617170` também passou integralmente.

Para PM-LOCAL-VALIDATION-002:

- evidência física inicial: ambiente e suíte PASS, mas teardown Playwright sujo após o resultado;
- correção: probe Playwright isolado em subprocesso;
- regressão automatizada adicionada;
- CI do PR #13: run `31448585330`, `396 passed`, zero failures;
- merge: `4ff470250bc7868f41846488fcfd1c1b4be24fd3`;
- repetição no host Linux/X11 real com Python 3.12.3: `396 passed`, todos os pré-requisitos PASS e encerramento limpo em `RESULTADO: PRONTO PARA TESTE FÍSICO`.

O smoke físico do Durable Journal/fault injection ainda não foi executado. A máquina local está agora validada e liberada para iniciar essa bateria controlada.

## Situação

PM-LOCAL-VALIDATION-002 está comprovada também no host físico real. O próximo passo é executar o smoke físico controlado do Durable Journal: cenário normal primeiro e, somente após PASS, crashes reproduzíveis com `falha-robo`, um checkpoint por vez, conforme `docs/NEXT.md`.
