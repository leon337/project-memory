# PM-HOME-IMPLEMENT-001 — Patrícia — Debugging e Análise de Falhas

## agent
Patrícia — Debugging e Análise de Falhas.

## scope
Capturar falhas reais do ciclo e localizar causa raiz sem mascarar FAILs.

## failure_1
O primeiro teste `exatamente:` falhou como previsto. A inspeção encontrou duas fronteiras independentes capazes de corromper o payload:
- `_extract_written_text()` em `goal_interpreter.py`;
- `plan_local_sequence()` em `policy.py`.

## failure_2
Depois da primeira correção, o CI run `31364265999` / run 291 continuou em `FAILURE`.

Causa raiz adicional: o comando natural usa `"um editor de texto"`; a canonicalização existente removia `o/a`, mas não `um/uma`, produzindo target diferente de `editor` no fast path.

Recuperação: normalização do artigo no ponto de parsing determinístico, sem ampliar a Policy Layer nem criar allowlist nova.

Resultado: CI run `31364557832` / run 292 = `SUCCESS`.

## failure_3
O primeiro ciclo completo da Home V4.1 registrou CI run `31365359561` / run 297 = `FAILURE` após substituição estrutural da Home. A causa era regressão de contrato dos testes legados de dashboard, não falha do Goal Runtime. Os testes foram atualizados para a nova superfície mantendo os endpoints tipados e os invariantes antigos relevantes. Run `31365499078` / run 298 = `SUCCESS`.

## failure_4
O teste de privacidade da conversa, run `31365593830` / run 299, falhou porque a primeira implementação tinha versão de contexto baseada em `hash()`/metadados e não sanitizava a mensagem do usuário antes do provider. A correção adotou SHA-256 estável do contexto sanitizado e `redact_text()` no prompt do usuário. Run `31365721132` / run 300 = `SUCCESS`.

## failure_5
O teste de não exposição de lease, run `31365982438` / run 301, falhou como esperado: `/api/status` ainda propagava `lease_token`/`lease_expires_at`. A fronteira pública passou a removê-los. Run `31366142008` / run 302 = `SUCCESS`.

## failure_6
O primeiro teste Chromium da Home, run `31366728644` / run 305, falhou porque foi usada uma fixture `page` que exigiria `pytest-playwright`, dependência não instalada. A recuperação manteve a dependência existente `playwright` e passou a abrir Chromium diretamente com `sync_playwright()`.

## decision
`PASS_WITH_CHANGES`

As falhas foram classificadas e recuperadas dentro do escopo já autorizado. Nenhuma exigiu HUMAN_GATE.

## artifact
Este relatório de debugging + commits/testes associados.

## handoff
Patrícia → Rafael/Helena/Renato.

Entrega: causas raiz e recuperações documentadas.
Próxima ação: revalidar o HEAD após as correções e continuar somente se o CI retornar verde.
Critério: zero FAIL automatizado conhecido no HEAD candidato.
