# CRASH / RECOVERY MATRIX

## Contrato

| Fronteira | Estado durável esperado | Recovery |
|---|---|---|
| antes da ação | `prepared` | pode entrar no backend quando lease novo é válido |
| durante/ao redor da ação | `in_flight` | não repeat-safe: bloquear/reconciliar; repeat-safe: pode repetir |
| após efeito/retorno, antes de receipt | `in_flight` | bloquear replay não repeat-safe |
| após receipt, antes do ACK | `executed` | não reemitir; recuperar safe receipt e observar novamente |
| após ACK | task terminal + `acknowledged` ou reconciliável | nunca reclaimar; startup corrige journal se necessário |

Nenhum caso permite `succeeded` apenas pelo estado do journal.

## Evidência física Linux/X11

| Cenário | Task | Evidência observada | Veredito |
|---|---|---|---|
| normal | `3e5e77ac-deda-4ac1-abf2-9188532efbc1` | Xed abriu, `JOURNAL-SMOKE-NORMAL-001` apareceu uma vez, readback confirmado e GoalVerifier `SUCCEEDED` | PASS |
| `after_backend` | `b0148f8c-4bfd-42f8-bb73-7ca243c68a8c` | efeito físico já podia ter ocorrido; no reclaim `open_app` estava `in_flight`, replay foi bloqueado e a task terminou `failed` fail-closed | PASS de segurança |
| `after_executed` | `6d07986b-5865-46bc-ac36-375b22c498e1` | Xed permaneceu aberto; após reclaim a tentativa 2 não reemitiu `open_app`, observou o Xed existente e terminou `succeeded` | PASS |
| `after_prepare` | `c376e052-8d72-4a5f-b768-e603672df252` | crash ocorreu antes do backend e Xed não abriu; após reclaim a tentativa 2 abriu uma única vez e terminou `succeeded` | PASS |
| `after_in_flight` | `8e993f29-273c-4024-9219-f4503ece4600` | crash ocorreu com estado durável `in_flight`; após reclaim houve `ActionReplayBlocked`, Xed não abriu e a task terminou `failed` | PASS de segurança |
| `before_ack` | `3b55952e-2e99-4d86-8d1b-f537111e5c12` | Xed abriu e houve sucesso local, mas crash ocorreu antes do ACK; após reclaim a tentativa 2 não mostrou nova abertura física e terminou `succeeded` após nova observação | PASS |
| `after_ack` | `39cbc255-ee3b-4c83-a34b-678883993a47` | Central marcou `succeeded` na tentativa 1 antes do crash; após religar o Robô a task permaneceu terminal, sem tentativa 2, sem reclaim e sem nova abertura física observada | PASS |

## Conclusão

A matriz física está completa no host Linux/X11 real. Os checkpoints `prepared`, `in_flight`, `executed`, pré-ACK e pós-ACK preservaram as invariantes previstas: ações não repeat-safe não são repetidas cegamente, estados ambíguos falham fechados, `executed` exige nova percepção independente e uma task já terminal após ACK não volta à fila.
