# MISSION TRACE

- Fonte canônica recuperada: STATUS → ARCHITECTURE → DECISIONS → NEXT.
- Issue #8 confirmada como OPEN / DISCOVERY — CONTRACT_MAPPING no início.
- MCF vigente consultado antes da implementação.
- Base main: `1e6d74b2f3314187a2967a7d38218dcc68dcc3b9`.
- Branch: `codex/pm-durable-journal-001`.
- PR draft: #9.
- Mapping levou à decisão de não criar estado VERIFIED no journal.
- Primeira implementação introduziu lifecycle durável e testes.
- Revisão de risco encontrou dois pontos e os corrigiu antes do closeout: action_key não poderia depender só de ocorrência; task antiga sem journal não poderia ser reexecutada.
- Fingerprint task-scoped e migração fail-closed foram adicionados.
- Validação final depende do CI do HEAD de closeout; smoke físico novo não é alegado sem acesso ao host.
