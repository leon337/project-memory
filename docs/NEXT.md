# NEXT

## 1. Atualizar e repetir `validar-robo` no mesmo host físico

O primeiro `validar-robo` real no Linux/X11 com Python 3.12.3 encontrou um teardown assíncrono do Playwright depois de imprimir PASS. A correção PM-LOCAL-VALIDATION-002 já está na `main`.

Como o host já possui os comandos oficiais, executar somente `atualizar-robo` e depois `validar-robo`.

Só avançar se a execução terminar realmente limpa em `RESULTADO: PRONTO PARA TESTE FÍSICO`, sem `Task was destroyed`, `TargetClosedError` ou outra exceção após o resultado.

## 2. Executar o smoke físico controlado do Durable Journal no Linux/X11

Executar um cenário normal primeiro e, somente após PASS, testar crashes reproduzíveis com `falha-robo`, um checkpoint por vez. A prova principal deve demonstrar no fluxo real Painel → Central → Robô que uma ação não repeat-safe não é emitida duas vezes após crash/restart/reclaim.

Estados ambíguos continuam fail-closed. Ação física, SQLite, journal, lease e restart devem ser reais; não declarar PASS físico a partir de fake/CI.

## 3. Após o PASS físico, decidir a próxima evolução

Prioridades candidatas: implementar o primeiro item do `docs/VALIDATION-ROADMAP.md` (`teste-robo`, bateria guiada) ou expandir capabilities/replanning. Qualquer capability que precise repetir legitimamente duas ações físicas idênticas na mesma task deve fornecer identidade estável explícita de contrato, sem reintroduzir contador implícito de retry.
