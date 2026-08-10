# PHASE PM-RELIABILITY-FOCUS-001 — DECISIONS

## D1 — Não remover o fail-closed
A correção estabiliza o alvo antes de armar teclado. Uma mudança real de foco depois do arming continua recusando entrada.

## D2 — Identidade de aplicativo conhecida usa WM_CLASS
Para aplicativos conhecidos, uma superfície com WM_CLASS incompatível não pode virar alvo de teclado.

## D3 — Smoke repetido reabre o editor a cada rodada
As cinco instâncias de editor são intencionais: cada rodada precisa reexercitar startup, aquisição de foco, digitação, GoalVerifier e readback AT-SPI.

## D4 — Execução contaminada não vale como gate limpo
A tentativa em que o operador interagiu com teclado foi preservada como evidência, mas excluída do critério de 5/5 consecutivos.

## D5 — Gate físico satisfeito
A segunda tentativa, sem interação do operador, passou 5/5 rodadas consecutivas e produziu `PASS_GATE: FOCUS_STABILITY_PHYSICAL`.

## D6 — Integração é gate interno
Com CI verde, auditoria final e gate de Léo aprovados, não existe HUMAN_GATE adicional para o merge desta correção.
