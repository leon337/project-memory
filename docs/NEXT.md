# NEXT

## 1. Concluir o recovery de `after_prepare`

A primeira metade física já passou: task `c376e052-8d72-4a5f-b768-e603672df252` caiu em `prepared`, Robô ficou OFFLINE, Central permaneceu ONLINE e o Xed não abriu antes do crash.

Religar somente o Robô pelo Painel e aguardar o reclaim da mesma task. Critério de PASS: a task retorna como tentativa 2, o estado `prepared` permite chamar `open_app` uma única vez, o Xed abre somente após o restart e a task conclui de forma coerente com percepção independente e GoalVerifier.

## 2. Validar `after_in_flight`

Depois do PASS completo de `after_prepare`, fechar o Xed, armar `falha-robo armar after_in_flight` e repetir exatamente `Abra o editor de texto`. Critério de PASS: a task recuperada encontra estado ambíguo `in_flight` e falha fechada com `ActionReplayBlocked`, sem reemitir fisicamente `open_app`.

## 3. Depois continuar `before_ack` e `after_ack`

Executar um checkpoint por vez. `before_ack` deve provar que uma task já executada/verificada não repete efeito físico enquanto aguarda aceitação terminal; `after_ack` deve provar que task terminal não é recuperada/reexecutada. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem prova no host.