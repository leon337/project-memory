# PM-HOME-REVIEW-001 — Context Baseline

**Agente:** Miriam — Memória e Gestão do Conhecimento  
**Fase:** revisão documental / retomada  
**Mission issue:** #1  
**Branch:** `review/pm-home-review-001`  
**Baseline project-memory:** `48712501f7d0ebc7e73e1be64d101ee40dd7aa5e`  
**Baseline MCF:** `1c58b4ba280bd32f587c2f042e35a2dba1a123a9`

## 1. Fontes consultadas

### MCF
- `README.md`
- `docs/protocols/MCF-PROTOCOLO-OPERACIONAL-UNIFICADO-DE-AGENTES.md`
- `docs/matrices/MCF-MATRIZ-CONSOLIDADA-DE-COMPETENCIAS-29-AGENTES.md`

### project-memory
- `README.md`
- `docs/STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `docs/NEXT.md`
- `src/context_anchor/dashboard.py`
- `src/context_anchor/goal_interpreter.py`
- `src/context_anchor/goal_runtime.py`
- `tests/test_dashboard.py`
- `tests/test_goal_interpreter.py`
- `.github/workflows/ci.yml`
- GitHub Actions do HEAD exato

## 2. Estado reconciliado

- O Goal Runtime universal está integrado ao fluxo real e `GoalVerifier` é a autoridade final de conclusão.
- `ExecutionReceipt` não satisfaz sozinho critérios finais; observação/readback independente é exigida.
- A suíte CI do HEAD do baseline está verde com 351 testes aprovados e 1 warning de depreciação externo.
- O projeto permanece localhost por padrão; acesso remoto é decisão separada.
- A janela residual de crash/replay continua registrada em `docs/NEXT.md`: falta journal/idempotência persistente por `task_id` + `action_key`.

## 3. Contradições e gaps atuais confirmados

### Drift documental
`README.md` ainda descreve a integração do Goal Runtime como próximo passo, enquanto `docs/STATUS.md` e `docs/ARCHITECTURE.md` registram a integração e validação como concluídas. O README não pode ser usado isoladamente para reconstruir o estado real.

### Fidelidade `exatamente:` — finding estático para revisão técnica
A função `_extract_written_text()` em `goal_interpreter.py` remove prefixos de editor e `texto:`, mas não remove o modificador natural `exatamente:`. O caso `Abra um editor de texto e escreva exatamente: Validação real número 1` não aparece na bateria atual de `tests/test_goal_interpreter.py`. Isso deve ser reproduzido e tratado por engenharia/testes antes de qualquer implementação da nova Home.

### Fronteira do Painel — finding estático para revisão de segurança
`dashboard.py` expõe rotas POST locais para iniciar/parar/reiniciar componentes, alternar desktop, acionar/limpar emergência e submeter tarefas. Não foram encontradas, nesse arquivo, camadas explícitas de autenticação do Painel, Origin/CSRF ou Trusted Host. O risco e a mitigação adequados devem ser determinados pelo especialista de segurança considerando que o serviço é localhost.

## 4. Estado da missão de revisão

Antes da missão, o repositório não possuía issues nem PRs e tinha apenas `main` e `codex/goal-runtime-wip`, ambas no mesmo SHA do baseline.

A missão agora possui:
- issue `#1`;
- branch documental `review/pm-home-review-001` criada a partir do baseline exato;
- nenhuma alteração funcional;
- nenhum merge.

## 5. Continuidade e proveniência

As propostas V1–V4 permanecem entradas visuais fornecidas por LEANDRO na conversa. V4 é candidata, não decisão final.

A revisão deve conservar a separação entre:
- fatos verificáveis no repositório;
- findings derivados por análise estática;
- recomendações ainda não aprovadas;
- decisões reservadas ao HUMAN_GATE de LEANDRO.

## 6. Independência operacional

Nesta execução, os papéis do MCF são segmentados funcionalmente e deixam entregas auditáveis e rastreáveis. Não há, nesta sessão, prova de runtimes cognitivos isolados por agente; portanto nenhuma independência cognitiva separada é alegada.

## 7. Handoff recomendado

Próximo: Leonardo — Produto e requisitos.

Entrada para Leonardo:
- objetivo da missão e quatro propostas visuais;
- baselines exatos;
- estado real reconciliado;
- findings atuais confirmados ou encaminhados;
- proibição de alteração funcional antes do HUMAN_GATE.

Critério para retorno: definir o papel da Home, prioridades do operador e critérios de produto para comparação V1–V4 sem transformar recomendações em decisão final.
