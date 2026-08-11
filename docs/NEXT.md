# NEXT

## 1. Validar `before_ack`

No host Linux/X11 já validado, fechar qualquer Xed anterior, armar `falha-robo armar before_ack` e executar exatamente `Abra o editor de texto` pelo Painel.

Critério de PASS: a ação física pode ocorrer e ser verificada, mas o Robô deve cair antes de a Central aceitar o resultado terminal. Após restart/reclaim, a mesma task não pode repetir fisicamente `open_app`; receipt recuperado continua insuficiente sozinho, e nova percepção/GoalVerifier devem confirmar o estado real antes de qualquer conclusão.

## 2. Validar `after_ack`

Somente após PASS completo de `before_ack`, armar `falha-robo armar after_ack` e repetir o mesmo objetivo. Critério de PASS: depois que a Central já aceitou o resultado terminal, a task permanece terminal após o crash/restart, não volta à fila e não reexecuta efeito físico.

## 3. Encerrar a matriz física e restaurar o ambiente local

Depois do PASS de `after_ack`, consolidar as evidências da matriz completa no STATUS e artefatos pertinentes, confirmar que não há checkpoint pendente e então restaurar com segurança o stash temporário dos arquivos locais criado antes da atualização. Não remover o stash antes dessa conferência final.