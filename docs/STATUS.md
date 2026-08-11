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
- PM-LOCAL-VALIDATION-001 integrado na `main` pelo PR #11, com atualização/validação local simplificadas e fault injection físico controlado.

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
- a inicialização foi corrigida com defaults locais compatíveis, sem alterar o contrato real de `LocalAgentSettings`;
- o CI final do PR, run `31447526239`, passou instalação, Playwright, compilação e suíte completa;
- resultado da suíte: `395 passed`, zero failures;
- o PR #11 foi integrado por squash na `main` como commit `e3b2a7ed31d4c18985bd2423169c06b42cf90a7b`;
- o CI pós-merge da `main`, run `31447617170`, também passou integralmente.

A cobertura nova inclui proteção do updater contra working tree suja e commits locais não publicados, fast-forward seguro, consumo one-shot do armamento, sanitização do evento e checkpoints antes/depois da chamada física.

Nenhum novo smoke físico do Durable Journal/fault injection no desktop Linux/X11 é alegado ainda. Essa prova exige o host físico real e permanece como próximo passo operacional.

## Situação

PM-LOCAL-VALIDATION-001 está integrado na `main`; o issue #10 foi encerrado como `completed`. Não há blocker técnico conhecido para iniciar a validação local. O próximo passo humano é fazer o bootstrap local uma única vez, executar `validar-robo` e, somente com resultado verde, iniciar a bateria física controlada descrita em `docs/NEXT.md`.
