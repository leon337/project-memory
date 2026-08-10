# MIGRATION / ROLLBACK

## Migração
- adição de `tasks.journal_version`;
- criação idempotente de `action_journal` e índice;
- legacy `running` ou `queued` com `attempts>0` e sem journal: failed closed;
- legacy queued nunca iniciada: pode ser claimada e marcada v1.

## Rollback
Rollback de binário é tecnicamente possível porque as alterações são aditivas, mas voltar a uma versão que ignora o journal reabre o risco de replay. Portanto rollback de código para uma versão pré-journal NÃO é considerado rollback seguro operacional enquanto houver tasks/journal ativos.

Rollback seguro exige: parar o Robô, preservar DB/backup, terminalizar/reconciliar tasks ambíguas e só então usar versão anterior. A tabela extra pode permanecer sem prejudicar leitores antigos que usam colunas nomeadas.
