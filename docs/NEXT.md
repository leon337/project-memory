# NEXT

## 1. Corrigir os três FAILs físicos confirmados

Usar a bateria de 2026-08-09 registrada em `docs/STATUS.md` como reprodução obrigatória.

Corrigir, sem criar falso `succeeded`:

- condicional `example.com`: o branch acessível é escolhido, mas `site acessível` não é escrito/readback corretamente e `text_present` fica pendente;
- busca informacional de São Lourenço da Mata: a página real abre com resultados, mas a percepção estruturada do DuckDuckGo falha com `não produziu resultados estruturados verificáveis`;
- contexto `lá`: quando não existe `LOCATION` válido, não substituir por `SUBJECT` arbitrário; falhar fechado ou resolver apenas com artefato semanticamente compatível.

Critério: repetir os testes 6, 7 e 8 pelo fluxo Painel → Central → Robô e obter estado final correto comprovado por evidências.

## 2. Completar a bateria física obrigatória e regressões

Após os três reparos:

- repetir os PASS já obtidos para garantir ausência de regressão;
- executar os casos restantes de `docs/CODEX_GOAL_RUNTIME_MISSION.md` que ainda não foram comprovados nesta bateria, incluindo navegação/browser específico e necessidade vaga de anotação, se aplicável;
- confirmar que nenhum caminho marca `succeeded` com critério obrigatório pendente;
- validar contexto entre tasks apenas depois de uma task anterior realmente `succeeded` e publicar o artefato correto.

## 3. Fechar tecnicamente e promover para `main`

Quando toda a bateria obrigatória estiver PASS:

- rodar suíte completa;
- compilação/check equivalente;
- `git diff --check`;
- revisão do diff e arquivos não relacionados;
- CI da versão candidata;
- atualizar `STATUS.md`, `ARCHITECTURE.md`, `DECISIONS.md` e este `NEXT.md`;
- commit/push final da branch;
- promover/mergear para `main` somente sem FAIL obrigatório conhecido;
- confirmar SHA remoto e CI final.
