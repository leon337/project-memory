# PHASE PM-HOME-IMPLEMENT-001 — DECISIONS

1. Mestre abriu missão Classe C em branch separada e PR draft.
2. Miriam reconciliou baseline, revisão V4.1 e fonte de verdade.
3. Rafael/Patrícia/Renato executaram TDD de `exatamente:` e `um editor` até GREEN.
4. Helena implementou a Home V4.1.
5. Tiago implementou Conversation Service isolado e fallback de providers.
6. Ricardo endureceu Host/Origin/headers e removeu lease do status público.
7. Beatriz/Júlia/Augusto/Sofia validaram comportamento, governança, rastreabilidade e arquitetura.
8. Vinícius realizou revisão inicial sem blocker, condicionada ao teste físico.
9. Emily/Léo liberaram avanço ao gate físico sem HUMAN_GATE.
10. Primeira execução física controlada capturou troca de foco; o Robô falhou fechado.
11. `FOCUS-RACE-001` foi registrado na Issue #4 como débito de confiabilidade.
12. Nova execução física atingiu `PASS_GATE`, mas uma execução de conversa revelou `CONVERSATION-IDENTITY-001`.
13. Tiago endureceu a identidade canônica `project-memory` sem transformar a conversa em resposta local fictícia.
14. Beatriz/Renato converteram o finding em regressões; CI final do código run 347 = SUCCESS.
15. Como houve mudança na Conversation API após o primeiro PASS físico, Mestre exigiu repetição no HEAD exato.
16. LEANDRO sincronizou a branch, reinstalou o pacote e repetiu o validador no Linux/X11.
17. Resultado físico final: `PASS_GATE: HOME_V4_1_PHYSICAL`, Z.AI/GLM real, GoalVerifier `verified=true`, readback AT-SPI exato e editor corroborando o texto.
18. Vinícius re-review `4895247454`: `PASS_FINAL`.
19. Emily: `PASS_FINAL_WITH_TRACKED_RELIABILITY_DEBT`; Issue #4 permanece aberta.
20. Léo: `APROVAR`; `HUMAN_GATE: NOT_REQUIRED`; merge autorizado após PRF final + CI do HEAD documental.
21. Gabriel/Carmem: finalizar PRF sem mudança de código; CI do novo HEAD é condição obrigatória antes de marcar ready/merge.
