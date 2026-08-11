# NEXT

## 1. Concluir `after_in_flight`

A primeira metade física já passou: task `8e993f29-273c-4024-9219-f4503ece4600` caiu na tentativa 1 depois de persistir `in_flight`, antes da chamada ao backend no checkpoint controlado; Central ficou online, Robô offline e Xed não abriu.

Agora religar somente o Robô pelo Painel. Não abrir o Xed manualmente e não enviar outra tarefa. A task pode permanecer `running` na tentativa 1 até o lease expirar; aguardar o reclaim normal.

Critério de PASS: a mesma task volta como tentativa 2, encontra estado durável ambíguo `in_flight`, gera `ActionReplayBlocked`, não emite fisicamente `open_app` e termina `failed` fail-closed. Esse `failed` é o resultado correto de segurança.

## 2. Validar `before_ack`

Somente após PASS completo de `after_in_flight`, executar `falha-robo armar before_ack` em um cenário controlado. Critério: ação física e verificação podem ter concluído, mas a queda antes da aceitação terminal da Central não pode causar replay do efeito físico no reclaim. Receipt recuperado continua insuficiente sozinho; percepção/GoalVerifier e estado terminal da Central permanecem autoridades.

## 3. Validar `after_ack`

Depois do PASS de `before_ack`, executar `falha-robo armar after_ack`. Critério: depois que a Central aceitou o resultado terminal, a task não pode voltar para a fila nem reexecutar efeito físico após restart. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem prova no host.