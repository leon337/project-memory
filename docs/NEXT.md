# NEXT

## 1. Executar a bateria física integrada A–E

Usar `docs/CODEX_GOAL_RUNTIME_MISSION.md` como contrato.

Executar pelo fluxo real Painel → Central → Robô os 10 testes obrigatórios, incluindo:

- editor + `Olá mundo`;
- navegação e busca;
- VS Code;
- necessidade vaga de cálculo;
- necessidade vaga de anotação;
- significado de Josiel;
- pesquisa → primeiro resultado → editor → escrita comprovada;
- condicional de `example.com`;
- contexto entre tasks com `lá`.

Critério: cada PASS precisa de estado final observado/evidência do Goal Runtime, não apenas ausência de exceção.

## 2. Corrigir qualquer FAIL real e fechar validação técnica

Para cada falha física, classificar a causa (interpretação, capability, provider, percepção, execução, evidência, contexto, lease ou progresso), corrigir e repetir o teste afetado.

Depois rodar:

- suíte completa;
- compilação/check equivalente;
- `git diff --check`;
- revisão do diff;
- CI da versão candidata quando houver push apropriado.

Não mergear enquanto existir FAIL obrigatório ou falso `succeeded` conhecido.

## 3. Fechar a missão e promover para `main`

Quando todos os critérios passarem:

- atualizar `STATUS.md`, `ARCHITECTURE.md`, `DECISIONS.md` e este `NEXT.md` para o estado final;
- garantir que apenas código/testes/docs da missão entrem;
- commit/push final;
- merge/promover para `main`;
- confirmar SHA remoto e CI;
- registrar qualquer limitação real restante.
