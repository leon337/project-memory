# NEXT

## 1. Validar `after_ack`

No host Linux/X11 já validado, fechar qualquer Xed anterior, armar `falha-robo armar after_ack` e executar exatamente `Abra o editor de texto` pelo Painel.

Critério de PASS: a ação física ocorre, a percepção/GoalVerifier concluem e a Central aceita o resultado terminal antes do crash. O fault injection deve então encerrar o Robô depois do ACK. Após restart, a mesma task deve permanecer terminal, não voltar à fila, não ganhar tentativa 2 e não reexecutar fisicamente `open_app`.

## 2. Consolidar a matriz física

Depois do PASS de `after_ack`, registrar no STATUS e artefatos pertinentes que cenário normal, `after_prepare`, `after_in_flight`, `after_backend`, `after_executed`, `before_ack` e `after_ack` foram executados fisicamente, distinguindo PASS de sucesso normal e PASS fail-closed onde aplicável. Confirmar que nenhum checkpoint ficou pendente.

## 3. Restaurar o ambiente local

Somente depois da consolidação final, restaurar com segurança o stash temporário criado antes da atualização, revisar conflitos/arquivos restaurados e confirmar que nenhum arquivo local foi perdido. Não remover o stash antes dessa conferência.