# NEXT

## 1. Executar o smoke físico normal do Durable Journal no Linux/X11

A validação local no host físico passou limpa com Python 3.12.3, `396 passed` e todos os pré-requisitos de desktop/X11 em PASS.

Executar primeiro um cenário normal pelo fluxo real Painel → Central → Robô, sem fault injection. Confirmar que uma tarefa física simples continua funcionando e que a ação não é emitida em duplicidade.

Só após PASS desse cenário normal avançar para crash testing.

## 2. Executar os crashes reproduzíveis com `falha-robo`

Armar um checkpoint por vez e repetir o fluxo real, mantendo ação física, SQLite, journal, lease, reclaim e restart reais. A prova principal deve demonstrar que uma ação não repeat-safe não é emitida duas vezes após crash/restart/reclaim.

Estados ambíguos continuam fail-closed. Não declarar PASS físico a partir de fake/CI.

## 3. Após o PASS físico, decidir a próxima evolução

Prioridades candidatas: implementar o primeiro item do `docs/VALIDATION-ROADMAP.md` (`teste-robo`, bateria guiada) ou expandir capabilities/replanning. Qualquer capability que precise repetir legitimamente duas ações físicas idênticas na mesma task deve fornecer identidade estável explícita de contrato, sem reintroduzir contador implícito de retry.
