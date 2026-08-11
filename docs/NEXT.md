# NEXT

## 1. Atualizar o host físico uma única vez para a versão com as novas ferramentas

Como a versão local anterior ainda não possui `atualizar-robo`, fazer apenas o bootstrap inicial necessário para trazer a `main` publicada e reinstalar o pacote editável. Depois desse bootstrap, a rotina recorrente passa a ser `atualizar-robo`.

Em seguida executar `validar-robo`. Só avançar ao smoke físico se o resultado for `PRONTO PARA TESTE FÍSICO`.

## 2. Executar o smoke físico controlado do Durable Journal no Linux/X11

Executar um cenário normal primeiro e, somente após PASS, testar crashes reproduzíveis com `falha-robo`, um checkpoint por vez. A prova principal deve demonstrar no fluxo real Painel → Central → Robô que uma ação não repeat-safe não é emitida duas vezes após crash/restart/reclaim.

Estados ambíguos continuam fail-closed. Ação física, SQLite, journal, lease e restart devem ser reais; não declarar PASS físico a partir de fake/CI.

## 3. Após o PASS físico, decidir a próxima evolução

Prioridades candidatas: implementar o primeiro item do `docs/VALIDATION-ROADMAP.md` (`teste-robo`, bateria guiada) ou expandir capabilities/replanning. Qualquer capability que precise repetir legitimamente duas ações físicas idênticas na mesma task deve fornecer identidade estável explícita de contrato, sem reintroduzir contador implícito de retry.
