# STATUS

## Objetivo atual

Manter um operador digital local que receba objetivos em linguagem natural, resolva capacidades disponíveis, execute em ciclo fechado e só persista `succeeded` quando o estado final estiver comprovado por evidências independentes.

## Estado verificável

O Goal Runtime universal está implementado e validado. A versão final foi preparada na branch de recuperação `codex/goal-runtime-wip`; no encerramento da missão, o mesmo SHA desta documentação é promovido para `main`.

O fluxo real vigente é:

```text
pedido
→ claim + lease heartbeat
→ contexto operacional curto
→ interpretação tipada ou decomposição estruturada
→ GoalContract / GoalRunState
→ Capability Resolver
→ Policy Layer
→ execução física
→ ExecutionReceipt
→ percepção independente
→ EvidenceRecord
→ GoalVerifier
→ continuar/falhar/succeeded
```

Não existe caminho autorizado a concluir uma task fora do `GoalVerifier`.

## Componentes integrados

- `goal_runtime.py` — contratos, critérios, subobjetivos, evidências, budgets e autoridade final de conclusão;
- `goal_execution.py` — orquestração universal dos fast paths e decomposições estruturadas;
- `goal_interpreter.py` — intents tipados com cobertura fail-closed;
- `planner.py` — decomposição estruturada, grounding e dataflow de artefatos;
- `capabilities.py` — descoberta de aplicativos por capability, PATH e XDG;
- `actions.py` / `desktop.py` — execução e percepção independente de navegador/X11/AT-SPI;
- `lease.py` — heartbeat e interrupção por perda de posse;
- `session_context.py` — contexto curto com origem, TTL e commit após ACK;
- `redaction.py` — sanitização de payloads, SQLite, contexto e logs;
- `local_agent.py` — integração do Goal Runtime ao fluxo Painel → Central → Robô.

## Invariantes de conclusão

- `ExecutionReceipt` registra a tentativa técnica, mas não comprova sozinho o efeito;
- todo critério obrigatório precisa de `observation` ou `readback` compatível;
- todos os subobjetivos obrigatórios precisam estar satisfeitos;
- contratos vazios, incompletos, cíclicos ou sem cobertura do objetivo falham fechados;
- `finish`, provider, fast path e executor não possuem autoridade final;
- ações físicas não idempotentes não são repetidas cegamente;
- Emergency Stop, FAILSAFE, foco e perda de lease atravessam fallback/retry.

## Validação automatizada final

Executada no ambiente local sobre o código candidato final:

- suíte completa: `351 passed`, `0 failed`, `1 warning` externo de depreciação Starlette/FastAPI;
- compilação sintática: `48` arquivos Python, `0` falhas;
- regressão relevante de Goal Runtime/browser/desktop/lease: `93 passed`;
- auditoria focada independente do diff: `72 passed`;
- `git diff --check`: aprovado;
- revisão independente do diff: nenhum blocker.

## Validação física integrada A–E

Os testes foram enviados pelo endpoint real do Painel e percorreram Painel → Central → SQLite/lease → Robô → GoalVerifier. Todos os 11 registros finais terminaram em uma tentativa, com `goal_completed=true`, `verified=true`, zero critérios/subobjetivos pendentes e observação/readback independente para cada critério obrigatório.

| Caso | Task ID final | Prova principal |
|---|---|---|
| A1 — Xed + `Olá mundo` | `5574f68e-39b8-4300-8a80-70295cada6a1` | janela X11 + readback AT-SPI exato de 9 caracteres |
| A2 — `globo.com` | `1442aa40-7ffd-4802-9b94-8aea874d249c` | DOM/URL final `globo.com`, HTTP 200 e target compatível |
| A3 — Brave + Google + consulta | `9ed375e7-c910-49a9-b8cb-43d415c8dcf9` | WM_CLASS, XID/PID/executável e omnibox AT-SPI com host/consulta exatos |
| B4 — VS Code | `4d857c39-9410-4d9b-9f39-4271d1e83294` | capability `code.edit` + janela/WM_CLASS observados |
| B5 — contas | `beae663b-320b-4024-8e37-ccdbc19536a7` | capability `calculate` resolveu GNOME Calculator instalada |
| B6 — anotação | `757d9cdb-3c26-4b8b-9eac-5a9cdcec6b43` | capability `text.edit` resolveu superfície Xed |
| B7 — significado de Josiel | `fba2a7a1-0518-40a8-b6a9-7efbec3649ef` | consulta, 10 resultados e informação relevante observados |
| C8 — pesquisa → título → editor | `8f049e19-146a-4b2f-80e8-fb87ee108896` | 5 critérios, 3 subobjetivos, artifact de 57 caracteres e readback exato |
| D9 — condicional `example.com` | `b9678059-6c54-4ef4-ab6e-693585b176ab` | condição HTTP 200, somente branch true e readback `site acessível` |
| E10a — contexto seed | `ef931cf6-3ef0-484b-8e55-770839d8a81f` | pesquisa observada e `location` persistida com origem |
| E10b — previsão de `lá` | `da30a0e1-3b0b-431c-b258-f1ba20924b03` | `lá` resolvido para E10a e resultados meteorológicos observados |

A consulta SQL universal de gate retornou `PASS_GATE` para os 11 IDs. Uma auditoria independente do SQLite também confirmou ausência de critério satisfeito apenas por receipt, evidence órfão, step falho ou falso `succeeded`.

## Falhas reais encontradas e corrigidas

- página Playwright antiga/fechada após processo ocioso: reinício controlado e validação do ciclo real;
- launcher Brave singleton encerra após repassar URL: a conclusão agora usa o pós-estado independente, não o PID efêmero;
- título de janela não prova host/consulta: a omnibox é lida somente por AT-SPI, fora do DOM, ligada ao XID, WM_CLASS e `_NET_WM_PID` corretos;
- ausência transitória de resultados HTML: Bing RSS é o quarto fallback estruturado e só é aceito quando content-type e raiz comprovam RSS/Atom;
- links Atom `self`: o parser prefere `rel=alternate` ou link sem `rel`.

## Segurança e privacidade preservadas

- Emergency Stop persistente e FAILSAFE físico;
- proteção de foco revalidada durante digitação;
- Policy Layer e `shell=False`;
- lease heartbeat e ACK atômico da Central;
- credenciais fora de código/Git/prompts/resultados;
- sanitização também na fronteira SQLite;
- Painel e Central em localhost por padrão;
- arquivos pessoais, PNGs, PDFs, análises externas e `egg-info` não entram no commit.

## Situação de conclusão

Os critérios obrigatórios de `docs/CODEX_GOAL_RUNTIME_MISSION.md` estão satisfeitos e não há FAIL obrigatório conhecido. Limitações evolutivas não bloqueantes estão registradas em `docs/NEXT.md`.
