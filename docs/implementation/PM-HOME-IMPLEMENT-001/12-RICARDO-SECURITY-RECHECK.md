# PM-HOME-IMPLEMENT-001 — Ricardo — Rechecagem Final de Segurança

## agent
Ricardo — Segurança.

## scope
Reavaliar o candidato depois da revisão de código e antes de qualquer teste físico/integração.

## evidence
O último HEAD funcional revisado é `ddb8e0d06c1981a592f26edbcb854e54046780a4`. Os commits posteriores até este artefato são documentação de evidência; não introduzem nova superfície de execução.

Controles verificados na implementação:
- Painel permanece vinculado por configuração a loopback;
- TrustedHost limita Host esperado;
- mutações browser-originated rejeitam Origin estrangeiro;
- `Sec-Fetch-Site: cross-site` sem Origin é recusado;
- CSP / frame deny / no-referrer / nosniff aplicados;
- Conversation API não possui acesso a Task API/executor;
- contexto e mensagem são sanitizados antes do provider;
- `.env` não é fonte de contexto;
- `/api/status` remove `lease_token` e `lease_expires_at`;
- Emergency Stop permanece caminho independente;
- nenhuma mudança em Policy Layer, GoalVerifier ou lease.

## automated_evidence
- cross-origin + trusted host: regressões em `tests/test_dashboard_v4_1.py`;
- lease exposure: TDD RED run 301 → GREEN run 302;
- contexto/user secret redaction: TDD RED run 299 → GREEN run 300;
- CI do HEAD funcional `ddb8e0...`: run 318 = SUCCESS.

## residuals
- inline JS/CSS é permitido pela CSP porque a aplicação é um documento local embarcado; não é autorização para Internet;
- credenciais reais de providers somente existem no `.env` local e não foram testadas no GitHub Actions;
- o teste físico ainda precisa confirmar o comportamento na máquina do operador.

## decision
`PASS_WITH_EXTERNAL_VALIDATION`

Nenhum blocker de segurança impede executar o validador físico local. Nenhum merge é autorizado por este parecer.

## artifact
Este documento.

## handoff
Ricardo → Carmem/Gabriel.

Entrega: segurança automatizada sem blocker conhecido.
Próxima ação: montar PRF Classe C e checkpoint de dependência física.
Critério: pacote de fase completo, PR draft preservado e estado físico explicitamente PENDING.
