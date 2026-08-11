# ARCHITECTURE

## Processos

```text
Painel do Robô :8765
├─ Conversar
│  └─ ProjectConversationService → providers
│     └─ sem TaskStore/executor físico
└─ Executar objetivo
   └─ Central :8000
      └─ SQLite: tasks + leases + action_journal
         └─ HTTP polling autenticado + heartbeat
            └─ Robô local
               └─ Goal Runtime
```

Painel, Central e Robô continuam processos separados. Localhost permanece o padrão.

## Goal Runtime

```text
objetivo
→ SemanticGoalInterpreter
→ GoalContract + GoalRunState
→ Capability Resolver quando necessário
→ Plan
→ Policy Layer
→ LeaseGuardedExecutor
→ Durable Action Journal
→ backend Playwright/Desktop
→ receipt técnico
→ percepção independente
→ EvidenceRecord
→ GoalVerifier
→ resultado sanitizado
→ ACK da Central
→ commit do Session Context
```

Fast paths determinísticos e decomposição por provider usam a mesma semântica de conclusão. Provider e ExecutionReceipt não possuem autoridade para declarar o objetivo concluído.

## Durable Action Journal

`action_journal.py` usa o mesmo SQLite da Central. A unidade durável é a chave composta `(task_id, action_key)`.

`action_key` é produzido pelo `LeaseGuardedExecutor` como fingerprint BLAKE2 task-scoped de `action + target`. O target bruto não vai para a coluna. A mesma ação+target na mesma task produz a mesma key; retry/reclaim não recebe uma identidade nova por contador implícito.

Estados:

```text
PREPARED
  journal gravado, backend não entrou
  ↓
IN_FLIGHT
  persistido antes da chamada externa/física
  ↓
EXECUTED
  chamada retornou + safe receipt persistido
  ↓
ACKNOWLEDGED
  Central aceitou estado terminal
```

Não existe `VERIFIED` no journal. Verificação continua no Evidence Ledger/GoalVerifier.

### Recovery

- `prepared`: pode prosseguir com lease válido porque a entrada no backend ainda não ocorreu;
- `in_flight` + não repeat-safe: fail-closed; não é possível atomizar SQLite com o mundo físico;
- `executed` + não repeat-safe: não reemite; retorna safe receipt ao fluxo para nova percepção independente;
- `acknowledged`: task terminal, nunca deve ser reclamada;
- crash entre `TaskStore.complete_task` e `journal.acknowledge_task`: startup da Central executa reconciliação de tasks terminais.

Apenas `active_window` e `capture_screen` são repeat-safe atualmente.

### Percepção de aplicativo após recovery de `executed`

O receipt recuperado de `open_app` continua sendo apenas registro técnico e não prova que a janela ainda existe. O fluxo tenta primeiro o observador normal de aplicação, que verifica a janela X11 ativa.

Se essa observação falhar **e somente se** o `LeaseGuardedExecutor` acabou de recuperar um `open_app` não repeat-safe já persistido como `executed`, entra um fallback passivo de recovery em `recovery_observation.py`:

```text
receipt recuperado de EXECUTED
→ NÃO reemitir open_app
→ observação normal da janela ativa
→ se insuficiente, enumerar janelas X11 já gerenciadas
→ comparar WM_CLASS com a identidade esperada
→ ler XID / título / _NET_WM_PID / /proc quando disponíveis
→ EvidenceRecord
→ GoalVerifier
```

Essa busca usa `_NET_CLIENT_LIST_STACKING`/`_NET_CLIENT_LIST` e é estritamente somente leitura: não lança processo, não ativa nem levanta janela, não muda foco, não clica e não digita. Isso permite reconhecer, por exemplo, um Xed que continua aberto enquanto o Painel/Brave ganhou foco durante o restart do Robô.

O fallback não é executado em operação normal nem em recovery `in_flight`; ele é condicionado ao marcador efêmero criado pelo recovery de `executed open_app`. Uma observação normal bem-sucedida consome esse marcador. ExecutionReceipt continua insuficiente e GoalVerifier permanece a única autoridade de conclusão.

## Fault injection físico controlado

`fault_injection.py` adiciona uma infraestrutura local de validação, não uma nova autoridade de execução.

O armamento é persistido em arquivo sob `runtime/`, fica desligado por padrão e não possui endpoint no Painel ou na Central. O comando local `falha-robo` pode armar um checkpoint one-shot.

Checkpoints:

```text
LeaseGuardedExecutor
  prepare journal
  → after_prepare
  transition in_flight
  → after_in_flight
  backend físico real retorna
  → after_backend
  transition executed
  → after_executed
  ... Goal Runtime / verifier ...
LocalAgent
  → before_ack
  POST resultado terminal para Central
  → after_ack
```

Ao atingir o checkpoint armado, `FaultInjectionController`:

1. consome atomicamente o arquivo de armamento;
2. grava um evento técnico sanitizado;
3. encerra somente o processo do Robô local com código próprio;
4. não rearma automaticamente no restart.

O controlador não simula mouse, teclado, navegador, SQLite, journal ou lease. Ele controla somente o instante do crash para tornar a prova física reproduzível.

`after_in_flight` é deliberadamente conservador: embora o checkpoint de teste ocorra antes da chamada do backend, o estado durável já é `in_flight`; um processo recuperado deve julgar apenas o que está persistido e, para ação não repeat-safe, falhar fechado.

## ACK e Session Context

ACK é a resposta terminal aceita pela Central depois de `TaskStore.complete_task` validar lease/token/expiração. Contexto entre tasks só é commitado após esse ACK.

O journal é marcado `acknowledged` depois da terminalização da task. Isso não é uma transação distribuída; a segurança vem do fato de a task já ser terminal e da reconciliação no startup.

Os checkpoints `before_ack` e `after_ack` existem apenas para validação controlada e não alteram a ordem normal de terminalização/context commit.

## Persistência e migração

`tasks` mantém a fila `queued → running → succeeded|failed` e recebe `journal_version`.

Migração:

- banco novo: tasks journal v1 desde a criação;
- banco antigo: `journal_version=0` para rows existentes;
- legacy nunca iniciada (`queued`, attempts=0): pode aderir a v1 ao claim;
- legacy já iniciada (`running` ou attempts>0): terminaliza `failed` por ambiguidade, sem replay.

`action_journal` possui PK `(task_id, action_key)`, timestamps, estado, flag repeat-safe e receipt JSON mínimo. Cleanup automático remove apenas `acknowledged` depois da retenção configurável, padrão 30 dias.

Fault injection não modifica o schema SQLite. Seus arquivos locais ficam em `runtime/`, que permanece fora do Git.

## Atualização e validação local

`maintenance.py` fornece duas interfaces operacionais instaladas com o pacote:

```text
atualizar-robo
validar-robo
```

### `atualizar-robo`

Fluxo:

```text
confirmar repositório/origin
→ exigir working tree limpa
→ fetch origin/main
→ bloquear main com commits locais não publicados
→ switch main
→ fast-forward only
→ criar/reusar .venv
→ pip install -e '.[dev]'
→ instalar/sincronizar Chromium do Playwright
→ mostrar commit instalado
```

Não há `reset --hard`, `git clean`, rebase automático ou reescrita de histórico.

### `validar-robo`

Valida sem executar ações físicas:

- repositório/branch/working tree;
- Python 3.11+;
- compilação `src + tests`;
- suíte pytest;
- backend desktop habilitado e sessão X11;
- PyAutoGUI, Pillow, PyScreeze, `xdotool` e `scrot`;
- Chromium do Playwright.

Só o resultado `PRONTO PARA TESTE FÍSICO` libera a bateria manual/real subsequente.

## Percepção e conclusão

ExecutionReceipt prova apenas execução técnica. Depois da ação o runtime usa observadores independentes:

- browser: DOM/URL/status/resultados;
- desktop: processo/X11/WM_CLASS;
- texto: AT-SPI/readback.

No recovery de um `open_app` já `executed`, a camada de lease pode complementar a observação ativa insuficiente com uma enumeração passiva de janelas X11 existentes; a evidência continua vindo do estado atual do sistema operacional, nunca do receipt recuperado.

EvidenceRecord liga a observação aos critérios. GoalVerifier exige todos os critérios/subobjetivos necessários antes de `SUCCEEDED`.

## Capability Resolver e ações

Capabilities atuais incluem `text.edit`, `calculate`, `web.search`, `web.read`, `browser.navigate` e `code.edit`.

Ações estruturadas atuais incluem `open_url`, `capture_screen`, `active_window`, `move_mouse`, `click_mouse`, `type_text`, `press_key`, `open_app` e `finish` interno.

## Segurança preservada

Permanecem obrigatórios:

- Policy Layer;
- lease/heartbeat;
- foco observável antes de teclado;
- FAILSAFE físico;
- Emergency Stop persistente;
- `shell=False`;
- percepção independente;
- redaction/whitelist nas fronteiras persistentes;
- credenciais fora de Git/logs/prompts;
- localhost por padrão.

Fault injection não é uma rota de operação normal, fica desarmado por padrão e não cria endpoint remoto. O journal, a observação passiva de recovery e as ferramentas de validação não enfraquecem nenhuma dessas barreiras e não criam um caminho paralelo de sucesso.

## Providers

Z.AI, Gemini e Cloudflare Workers AI permanecem providers intercambiáveis de interpretação/decomposição. Fast paths locais evitam provider quando a intenção é inequívoca. Providers não são autoridade de conclusão.
