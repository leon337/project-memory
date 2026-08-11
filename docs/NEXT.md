# NEXT

## 1. Concluir `before_ack`

A primeira metade física passou: task `3b55952e-2e99-4d86-8d1b-f537111e5c12` executou `Abra o editor de texto`, o Xed abriu, o Robô registrou resultado local de sucesso e caiu no checkpoint `before_ack` antes do aceite terminal da Central. Central permaneceu online, Robô ficou offline e a task ficou `running` na tentativa 1.

Agora religar somente o Robô pelo Painel. Manter o Xed aberto, não abrir outro editor manualmente e não enviar nova tarefa. A task pode permanecer `running` até o lease expirar.

Critério de PASS: a mesma task volta como tentativa 2 sem reemitir fisicamente `open_app`; o estado já existente deve ser observado novamente de forma independente e GoalVerifier deve produzir conclusão coerente. Receipt recuperado não pode, sozinho, autorizar sucesso.

## 2. Validar `after_ack`

Somente após PASS completo de `before_ack`, fechar o Xed anterior, armar `falha-robo armar after_ack` e repetir exatamente `Abra o editor de texto`. Critério de PASS: depois que a Central já aceitou o resultado terminal, a task permanece terminal após crash/restart, não volta à fila e não reexecuta efeito físico.

## 3. Encerrar a matriz física e restaurar o ambiente local

Depois do PASS de `after_ack`, consolidar as evidências da matriz completa no STATUS e artefatos pertinentes, confirmar que não há checkpoint pendente e então restaurar com segurança o stash temporário dos arquivos locais criado antes da atualização. Não remover o stash antes dessa conferência final.