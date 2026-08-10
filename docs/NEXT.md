# NEXT

## 1. Fazer smoke físico controlado do journal no host Linux/X11

A implementação e o fault injection automatizado cobrem as fronteiras de crash, mas esta execução não tinha acesso ao desktop físico do usuário. O próximo teste operacional deve comprovar no fluxo real Painel → Central → Robô que uma ação não repeat-safe não é emitida duas vezes após kill/restart/reclaim e que uma task normal continua funcional.

Esse smoke não muda o contrato: se o estado persistente ficar ambíguo, o comportamento esperado continua fail-closed.

## 2. Expandir capabilities/replanning somente com identidade durável explícita

Qualquer capacidade futura que precise executar legitimamente duas ações físicas idênticas na mesma task deve fornecer identidade estável de contrato para distinguir as duas invocações; não deve reintroduzir contador implícito de retry no journal.
