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

## ACK e Session Context

ACK é a resposta terminal aceita pela Central depois de `TaskStore.complete_task` validar lease/token/expiração. Contexto entre tasks só é commitado após esse ACK.

O journal é marcado `acknowledged` depois da terminalização da task. Isso não é uma transação distribuída; a segurança vem do fato de a task já ser terminal e da reconciliação no startup.

## Persistência e migração

`tasks` mantém a fila `queued → running → succeeded|failed` e recebe `journal_version`.

Migração:

- banco novo: tasks journal v1 desde a criação;
- banco antigo: `journal_version=0` para rows existentes;
- legacy nunca iniciada (`queued`, attempts=0): pode aderir a v1 ao claim;
- legacy já iniciada (`running` ou attempts>0): terminaliza `failed` por ambiguidade, sem replay.

`action_journal` possui PK `(task_id, action_key)`, timestamps, estado, flag repeat-safe e receipt JSON mínimo. Cleanup automático remove apenas `acknowledged` depois da retenção configurável, padrão 30 dias.

## Percepção e conclusão

ExecutionReceipt prova apenas execução técnica. Depois da ação o runtime usa observadores independentes:

- browser: DOM/URL/status/resultados;
- desktop: processo/X11/WM_CLASS;
- texto: AT-SPI/readback.

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

O journal não enfraquece nenhuma dessas barreiras e não cria um caminho paralelo de sucesso.

## Providers

Z.AI, Gemini e Cloudflare Workers AI permanecem providers intercambiáveis de interpretação/decomposição. Fast paths locais evitam provider quando a intenção é inequívoca. Providers não são autoridade de conclusão.
