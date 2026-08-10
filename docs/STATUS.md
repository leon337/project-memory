# STATUS

## Objetivo atual

Manter um operador digital local que receba objetivos em linguagem natural, converse sobre o próprio projeto sem executar ações por engano e execute objetivos físicos em ciclo fechado, persistindo `succeeded` somente quando o estado final for comprovado por evidências independentes.

## Estado verificável agora

A `main` contém a Home V4.1, o Goal Runtime universal e a correção de estabilidade de foco Linux/X11.

Integração funcional mais recente:

- PR #5 — `FOCUS-RACE-001` — merge funcional `b47d6a1ef9954e20d36593acfc050819bdb7c902`;
- correção: `StableFocusDesktopBackend` estabiliza o XID antes de armar teclado e valida `WM_CLASS` para aplicativos conhecidos;
- o guard fail-closed continua ativo depois do arming: mudança real de foco recusa teclado;
- Emergency Stop, FAILSAFE, Policy, lease e autoridade do GoalVerifier não foram enfraquecidos.

## Arquitetura operacional vigente

```text
Painel local :8765
├─ Conversar
│  └─ ProjectConversationService
│     └─ providers configurados localmente
│        └─ sem criar task nem executar mouse/teclado
└─ Executar objetivo
   └─ Central :8000
      └─ SQLite / fila / lease
         └─ Robô local
            └─ Goal Runtime
               └─ Policy
                  └─ execução física
                     └─ percepção independente
                        └─ GoalVerifier
```

A conversa e a execução são caminhos separados. O modo Conversar não possui `TaskStore`, executor físico ou autoridade para declarar conclusão de objetivo.

## Providers

O código suporta Z.AI, Gemini e Cloudflare Workers AI como providers. Credenciais são configuração local em `.env` e não entram no Git. A presença de suporte no código não significa que um provider esteja configurado na máquina.

## Validações concluídas

### Home V4.1

- fluxo real Painel → Central → Robô → GoalVerifier validado;
- conversa real isolada validada;
- `Validação real número 1` comprovada por GoalVerifier `verified=true` e readback AT-SPI exato;
- gate físico: `PASS_GATE: HOME_V4_1_PHYSICAL`.

### FOCUS-RACE-001

A primeira tentativa repetida foi contaminada por interação manual do operador e foi preservada como evidência, mas não usada como gate limpo.

A segunda tentativa foi executada sem interação manual:

- 5/5 rodadas físicas consecutivas PASS;
- cinco startups reais de editor;
- GoalVerifier `verified=true` em todas;
- readback AT-SPI exato em todas;
- gate físico: `PASS_GATE: FOCUS_STABILITY_PHYSICAL`.

A suíte automatizada do candidato chegou a `370 passed`; o HEAD de closeout do PR passou no CI run 357 antes do merge.

## Dívidas conhecidas não bloqueantes

- consolidar futuramente a tabela de identidades `WM_CLASS` hoje repetida em pontos do backend;
- ainda existe a janela residual de replay se houver crash abrupto depois de uma ação física e antes do ACK; a correção planejada é journal/idempotência persistente por `task_id + action_key`.

## Situação

Não há blocker conhecido para a correção de foco. A Issue #4 pode ser encerrada depois da verificação final da `main` documentada nesta sessão. O próximo trabalho está em `docs/NEXT.md`.
