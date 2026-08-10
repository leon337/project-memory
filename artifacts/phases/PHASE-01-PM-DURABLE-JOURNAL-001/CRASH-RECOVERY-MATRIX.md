# CRASH / RECOVERY MATRIX

| Fronteira | Estado durável esperado | Recovery |
|---|---|---|
| A. antes da ação | `prepared` | pode entrar no backend quando lease novo é válido |
| B. durante/ao redor da ação | `in_flight` | não repeat-safe: bloquear/reconciliar; repeat-safe: pode repetir |
| C. após efeito/retorno, antes de receipt | `in_flight` | bloquear replay não repeat-safe |
| D. após receipt, antes do ACK | `executed` | não reemitir; recuperar safe receipt e observar novamente |
| E. após ACK | task terminal + `acknowledged` ou reconciliável | nunca reclaimar; startup corrige journal se necessário |

Nenhum caso permite `succeeded` apenas pelo estado do journal.
