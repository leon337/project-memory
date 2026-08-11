# NEXT

## 1. Concluir `after_ack`

A primeira metade física passou na task `39cbc255-ee3b-4c83-a34b-678883993a47`: Xed abriu, a Central registrou `succeeded` na tentativa 1 e somente depois o checkpoint `after_ack` encerrou o Robô. Central permaneceu online e Robô ficou offline.

Agora religar somente o Robô pelo Painel. Manter o Xed aberto, não enviar outra tarefa e aguardar alguns instantes.

Critério de PASS final: a mesma task deve continuar `succeeded` na tentativa 1, não voltar para `running`/`queued`, não ganhar tentativa 2 e não reexecutar fisicamente `open_app`.

## 2. Consolidar a matriz física

Depois do PASS final de `after_ack`, registrar que cenário normal, `after_prepare`, `after_in_flight`, `after_backend`, `after_executed`, `before_ack` e `after_ack` foram executados fisicamente, distinguindo PASS normal e PASS fail-closed onde aplicável. Confirmar que nenhum checkpoint ficou pendente.

## 3. Restaurar o ambiente local

Somente depois da consolidação final, restaurar com segurança o stash temporário criado antes da atualização, revisar os arquivos restaurados e confirmar que nenhum arquivo local foi perdido. Não remover o stash antes dessa conferência.