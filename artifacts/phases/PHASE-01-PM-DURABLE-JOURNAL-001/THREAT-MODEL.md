# THREAT MODEL

## Ameaças tratadas
- crash entre efeito físico e ACK;
- lease expirado/reclaim por outro agente;
- receipt confundido com prova de efeito;
- replay de ação não idempotente em estado ambíguo;
- task legada sem journal;
- journal virando depósito de texto/URL/screenshot sensível;
- chamada de journal com lease velho.

## Controles
- journal na Central autenticada;
- lease vivo obrigatório para prepare/transition;
- `in_flight` não repeat-safe bloqueia replay;
- receipt whitelist no agente e novamente na Central;
- target bruto não é gravado no action_key; apenas fingerprint task-scoped;
- GoalVerifier continua exigindo percepção independente;
- ACK terminal precede elegibilidade de cleanup.

## Risco residual conhecido
Sem transação distribuída com o mundo físico, `in_flight` não pode distinguir com certeza “efeito ocorreu” de “efeito não ocorreu”. A resposta deliberada é reconciliação/fail-closed, não repetição otimista.
