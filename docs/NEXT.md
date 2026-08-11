# NEXT

## 1. Validar `after_prepare`

No host Linux/X11 já validado, fechar o Xed anterior, armar `falha-robo armar after_prepare` e executar exatamente `Abra o editor de texto` pelo Painel. Critério de PASS: o crash ocorre antes do backend físico; após restart/reclaim a mesma task pode executar `open_app` uma única vez e concluir de forma coerente com percepção independente e GoalVerifier.

## 2. Validar `after_in_flight`

Depois do PASS de `after_prepare`, repetir o cenário com `falha-robo armar after_in_flight`. Critério de PASS: a task recuperada encontra estado ambíguo `in_flight` e falha fechada com `ActionReplayBlocked`, sem reemitir fisicamente `open_app`.

## 3. Depois continuar `before_ack` e `after_ack`

Executar um checkpoint por vez. `before_ack` deve provar que uma task já executada/verificada não repete efeito físico enquanto aguarda aceitação terminal; `after_ack` deve provar que task terminal não é recuperada/reexecutada. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem prova no host.