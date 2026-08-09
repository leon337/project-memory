# STATUS

## Objetivo atual

Construir um operador digital local capaz de receber objetivos em linguagem natural, usar as capacidades disponíveis ao usuário e ao sistema operacional e continuar executando até concluir o objetivo.

## Estado verificável agora

O `main` contém o MVP 0.3 com três processos separados:

- **Painel do Robô** — `127.0.0.1:8765`;
- **Central** — `127.0.0.1:8000`;
- **Robô local** — polling autenticado, planejamento, execução, verificação e telemetria.

Painel e Central continuam locais por padrão. Publicação remota ainda não foi implementada.

## Capacidades físicas já validadas

No Linux/X11 real já foram validados controles de Painel/Central/Robô, Emergency Stop, FAILSAFE, screenshot, mouse, aplicativos, Unicode/teclado, proteção de foco, telemetria, planner multi-provider com fallback e fast paths locais de editor/escrita e navegação/pesquisa.

## Baseline físico de autonomia — conclusão

O executor físico e os fast paths já realizam ações úteis. Os principais FAILs atuais estão em:

- interpretação de intenção natural;
- resolução de capacidades/aplicativos;
- contexto entre tarefas;
- percepção de conteúdo;
- condicionais/replanejamento;
- falso `succeeded` em objetivos compostos.

Não é correto resolver autonomia adicionando regex por frase como estratégia principal.

### Regressão crítica

Pedido:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

Houve um falso PASS histórico: apenas a pesquisa foi aberta; o primeiro resultado não foi lido, o editor não foi aberto e o título não foi escrito. Esse caso é a regressão principal da nova arquitetura.

## Decisão arquitetural vigente — Goal Runtime universal

Foi adotado um **Goal Runtime universal em ciclo fechado**:

```text
Goal Contract
→ estado operacional / blackboard
→ resolução de capacidade
→ próxima etapa
→ Policy Layer
→ executor
→ Execution Receipt
→ observação
→ evidência
→ Goal Verifier
→ replanejamento ou conclusão
```

Princípios:

- fast paths continuam como skills/otimizações dentro do mesmo Goal Run;
- ação executada não equivale automaticamente a objetivo concluído;
- planner não possui autoridade final para `succeeded`;
- somente o Goal Verifier pode fechar o objetivo quando critérios obrigatórios estiverem comprovados;
- migração incremental, sem reescrever Painel, Central, SQLite/fila/leases, executores, Policy Layer, FAILSAFE, Emergency Stop ou providers.

## Fundação de código criada nesta sessão

Foi criado `src/context_anchor/goal_runtime.py` como fundação isolada, ainda **não conectada ao fluxo físico atual**.

Ela define:

- `GoalContract`;
- `GoalCriterion`;
- `GoalSubgoal`;
- `GoalRunState`;
- `EvidenceRecord`;
- `EvidenceKind`;
- `GoalVerdict`;
- `GoalVerifier`.

Semântica já travada:

- `ExecutionReceipt` registra execução técnica, mas não prova sozinho um efeito do objetivo;
- observação/readback verificado pode satisfazer um critério;
- critério obrigatório pendente mantém o Goal Run aberto;
- apenas todos os critérios obrigatórios comprovados permitem `SUCCEEDED`.

Foi criado `tests/test_goal_runtime_contract.py` com quatro regressões de contrato. Antes da publicação, a sintaxe foi compilada e quatro checks equivalentes foram executados isoladamente com sucesso.

Também foram atualizados:

- `ARCHITECTURE.md` — pipeline alvo e scaffold existente;
- `DECISIONS.md` — D-022 Goal Runtime universal e D-023 Execution Receipt não é evidência de efeito;
- `NEXT.md` — integração pesada no `local_agent`, percepção e autonomia sem frases cadastradas.

## O que deliberadamente não foi alterado ainda

A fundação nova não intercepta ainda:

- `local_agent.py`;
- planner atual;
- fast paths atuais;
- execução física;
- persistência final da Central.

Isso mantém o MVP funcional enquanto a integração pesada é preparada.

## Próxima fronteira pesada

Migrar `local_agent` para que todo pedido crie/use o mesmo Goal Run, convertendo fast paths e planner por IA em fontes de steps e fazendo o Goal Verifier ser a única autoridade de conclusão.

Depois: percepção estruturada, Capability Resolver, Session Context e Recovery Manager.

## Providers

O modo `multi` possui adaptadores para Z.AI/GLM, Google Gemini e Cloudflare Workers AI; Cloudflare ainda precisa do `Account ID` no ambiente real. Z.AI e Gemini apresentaram 429/respostas inválidas nos testes recentes, portanto fast paths determinísticos continuam importantes para preservar quota.

## Controles preservados

- parada de emergência persistente;
- FAILSAFE físico próprio nos quatro cantos;
- proteção de foco antes de teclado;
- `shell=False`;
- credenciais fora de código, Git, logs e prompts;
- Painel e Central em localhost por padrão.
