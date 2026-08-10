# PHASE DECISIONS

1. O journal fica no mesmo SQLite da Central; não há microserviço novo.
2. A máquina mínima é `prepared → in_flight → executed → acknowledged`; não existe estado `verified` no journal para não criar segunda autoridade de conclusão.
3. `in_flight` de ação não repeat-safe é ambíguo e fail-closed.
4. `executed` impede nova emissão da mesma ação; o receipt recuperado apenas permite nova percepção/verificação.
5. `action_key` é fingerprint task-scoped de ação+target, sem target bruto e sem contador de retry.
6. Apenas `active_window` e `capture_screen` são repeat-safe nesta fase.
7. ACK significa resposta terminal aceita pela Central. Se houver crash entre terminalização da task e marcação do journal, startup reconcilia.
8. Cleanup automático só remove `acknowledged` após retenção configurável, padrão 30 dias.
9. Task legada já iniciada sem journal é ambígua e falha fechada; legada nunca iniciada pode aderir ao journal v1.
