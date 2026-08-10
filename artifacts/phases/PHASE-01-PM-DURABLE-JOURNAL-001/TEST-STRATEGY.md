# TEST STRATEGY

Camadas:
1. Store/migração SQLite.
2. Lease + executor com fake físico contabilizável.
3. API Central autenticada.
4. Fault injection nas fronteiras A–E.
5. Regressão completa do repositório no CI.

Oráculos principais:
- número de chamadas físicas deve permanecer zero no replay bloqueado/recuperado;
- estado ambíguo deve falhar fechado;
- PREPARED pode continuar;
- receipt persistido não contém target bruto;
- ACK terminal torna journal `acknowledged`;
- legacy ambígua não volta para queued;
- GoalVerifier permanece necessário para sucesso.
