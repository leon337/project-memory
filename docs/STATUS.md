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
- PM-DURABLE-JOURNAL-001 implementado e rastreado pelo PR #9.

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

## Migração e compatibilidade

`tasks` recebe `journal_version` e `action_journal` é criada de forma aditiva.

- task legada nunca iniciada (`queued`, `attempts=0`) pode ser claimada e promovida para journal v1;
- task legada já iniciada sem journal é ambígua e recebe `failed` fail-closed, em vez de ser reclamada cegamente.

## Privacidade

O journal não persiste texto integral digitado, screenshot ou URL completa. Receipts passam por whitelist no agente e novamente na Central. Credenciais continuam fora de Git/logs/prompts.

## Validação

O implementation head `9558ddd04f852fb5835a960c7ab7adb1aef8f36b` passou no CI run `31438287389`.

A cobertura adicionada inclui:

- crash antes do backend;
- estado `in_flight` ambíguo;
- crash após retorno físico e antes do receipt durável;
- `executed` antes do ACK;
- reconciliação após terminal ACK;
- migração de tasks legadas;
- autenticação/lease da API do journal;
- sanitização do receipt;
- deduplicação da mesma ação+target.

Nenhum novo smoke físico no desktop Linux/X11 é alegado por esta missão, porque o ambiente instrumental desta execução foi GitHub/CI. A bateria física anterior da Home V4.1 permanece baseline histórica, não evidência desta alteração.

## Situação

Sem blocker técnico conhecido no código da missão. O closeout depende apenas de documentação/revisão final do PR e CI do HEAD final.
