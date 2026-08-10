# PM-RELIABILITY-FOCUS-001 — Vinícius — Code Review

## scope
Revisar o diff funcional da estabilização de foco.

## findings
- backend novo é extensão isolada do backend atual;
- caminho real do Robô usa `StableFocusDesktopBackend`;
- settling reinicia quando XID muda;
- WM_CLASS conhecida impede janela alheia de virar alvo;
- apps desconhecidos continuam possíveis por XID estável e guard posterior;
- regressões cobrem o caso reportado e casos adversariais;
- CI automatizado está verde.

Finding não bloqueante: a tabela de identidades WM_CLASS replica valores já usados por `observe_application`; consolidar futuramente reduzirá drift, mas a duplicação atual não afrouxa segurança.

## decision
`PASS_WITH_REQUIREMENTS`

## requirements
- smoke físico 5/5;
- zero falha `foco mudou` sem interação nas 5 rodadas;
- GoalVerifier + AT-SPI exatos em cada rodada;
- Emily + Léo depois da evidência física.

## handoff
Vinícius → Augusto/Emily após dependência física.
