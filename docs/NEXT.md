# NEXT

## 1. Validar `after_in_flight`

No host Linux/X11 já validado, fechar o Xed anterior, armar `falha-robo armar after_in_flight` e executar exatamente `Abra o editor de texto` pelo Painel.

Primeira metade esperada: o Journal já entra em `in_flight`, mas o fault injection encerra o Robô antes da chamada física ao backend neste checkpoint controlado; Xed não deve abrir antes do crash.

Após restart/reclaim, a mesma task deve encontrar estado durável ambíguo `in_flight` e falhar fechada com `ActionReplayBlocked`, sem emitir fisicamente `open_app`. Esse `failed` é PASS de segurança porque o sistema não pode provar se um efeito externo teria ocorrido numa queda real nesse estado.

## 2. Validar `before_ack`

Somente após PASS de `after_in_flight`, executar `falha-robo armar before_ack` em um cenário controlado. Critério: ação física e verificação podem ter concluído, mas a queda antes da aceitação terminal da Central não pode causar replay do efeito físico no reclaim. Receipt recuperado continua insuficiente sozinho; percepção/GoalVerifier e estado terminal da Central permanecem autoridades.

## 3. Validar `after_ack`

Depois do PASS de `before_ack`, executar `falha-robo armar after_ack`. Critério: depois que a Central aceitou o resultado terminal, a task não pode voltar para a fila nem reexecutar efeito físico após restart. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem prova no host.