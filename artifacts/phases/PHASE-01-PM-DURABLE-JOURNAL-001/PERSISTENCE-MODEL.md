# PERSISTENCE MODEL

Tabela `action_journal`:
- `task_id`;
- `action_key`;
- `action_name`;
- `repeat_safe`;
- `state`;
- `receipt_json` mínimo;
- `created_at`;
- `updated_at`;
- `acknowledged_at`;
- PK `(task_id, action_key)`.

Tabela `tasks` recebe `journal_version INTEGER NOT NULL`.

Migração é aditiva via SQLite. Existing rows recebem `journal_version=0`; rows novas usam 1. Legacy rows já iniciadas são terminalizadas como failed por ambiguidade. Legacy queued com attempts=0 pode ser claimada e promovida a v1.

Transações usam `BEGIN IMMEDIATE` nas mudanças do journal/claim relevantes e validam lease dentro da transação.
