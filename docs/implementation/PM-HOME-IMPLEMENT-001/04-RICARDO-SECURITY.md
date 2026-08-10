# PM-HOME-IMPLEMENT-001 — Ricardo — Segurança da Home V4.1

## agent
Ricardo — Segurança.

## scope
Endurecer a fronteira browser/localhost sem transformar o Painel em serviço remoto.

## changes
`dashboard.py` passou a aplicar:
- `TrustedHostMiddleware` para `127.0.0.1`, `localhost` e host de testes;
- rejeição `403` para mutações `/api/*` com Origin diferente do Host;
- rejeição de `Sec-Fetch-Site: cross-site` quando Origin estiver ausente;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: no-referrer`;
- `X-Frame-Options: DENY`;
- CSP restringindo default/connect/form/frame ao próprio Painel;
- preservação do bind loopback definido em `DashboardSettings`;
- remoção de `lease_token` e `lease_expires_at` da resposta pública `/api/status`.

## boundary_decision
Clientes locais não-browser continuam capazes de usar a API sem Origin; browsers cross-site são bloqueados. Isso preserva a operação local existente e adiciona proteção à superfície web.

`/api/conversation` permanece separado de `/api/tasks`; não existe caminho da Conversation API para `submit_task`, mouse, teclado, navegador ou subprocesso.

## evidence
- `test_browser_mutation_rejects_foreign_origin_but_allows_same_origin`;
- `test_untrusted_host_is_rejected`;
- `test_dashboard_status_never_exposes_task_lease_token`;
- TDD do lease: run `31365982438` / run 301 = `FAILURE`; correção: run `31366142008` / run 302 = `SUCCESS`.
- script físico também verifica cross-origin e ausência de lease antes da ação física.

## residual_risk
- a CSP ainda permite CSS/JS inline porque a Home é entregue como documento local embutido; isso é aceitável para a superfície loopback atual, mas não deve ser usado como justificativa para exposição Internet;
- rate limiting de conversa não é fronteira de autorização nesta versão local; quotas continuam responsabilidade do provider/configuração;
- acesso remoto continua fora de escopo.

## decision
`PASS_WITH_REQUIREMENTS`

Requisito restante: executar o smoke físico no ambiente Linux/X11 real antes do gate final.

## artifact
Hardening em `dashboard.py`, regressões de segurança e este relatório.

## handoff
Ricardo → Tiago/Beatriz.

Entrega: fronteira web local endurecida e segredos de lease removidos da telemetria pública.
Próxima ação: avaliar conversa com provider/contexto e provar ausência de execução física.
Critério: contexto sanitizado, zero task no modo Conversar e provider/modelo somente quando reais.
