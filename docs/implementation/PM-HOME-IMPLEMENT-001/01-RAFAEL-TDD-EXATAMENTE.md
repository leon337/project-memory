# PM-HOME-IMPLEMENT-001 — Rafael — TDD do modificador `exatamente:`

## agent
Rafael — Engenharia de Software.

## scope
Corrigir a fidelidade do payload de escrita antes do redesign funcional.

## action
Foi criado `tests/test_exact_modifier.py` com o comando real de aceite:

`Abra um editor de texto e escreva exatamente: Validação real número 1`

O teste exige:
- intent `OPEN_AND_WRITE`;
- `intent.text == "Validação real número 1"`;
- `Plan("open_app", "editor")`;
- `Plan("type_text", "Validação real número 1")`.

## evidence
- RED inicial: commit `a4f3e42a8cf2e2eb1e0ed06540ad32fa251f5214`; CI run `31363942980` / run 288 = `FAILURE`.
- Implementação compartilhou `strip_exact_write_modifier()` entre interpreter e policy.
- GREEN final do slice: commit `e43c948ccc7c1659c44701e9705c8d3837219eba`; CI run `31364557832` / run 292 = `SUCCESS`.

## changes
- `src/context_anchor/text_semantics.py` criado;
- `goal_interpreter.py` não incorpora `exatamente:` ao texto do Goal;
- `policy.py` não incorpora `exatamente:` ao `type_text` determinístico;
- artigo natural `um/uma` antes de `editor` é normalizado no fast path para preservar o target canônico `editor`.

## decision
`PASS`

## artifact
Código + regressão automatizada + este registro.

## handoff
Rafael → Renato/Patrícia.

Entrega: regressão reproduzida e correção candidata.
Próxima ação: validar CI e investigar qualquer falha remanescente sem alterar o critério esperado.
Critério: suíte verde mantendo payload exato e target `editor`.
