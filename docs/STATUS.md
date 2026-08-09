# STATUS

## Objetivo atual

Construir um operador digital local capaz de receber objetivos em linguagem natural, usar as capacidades disponíveis ao usuário e ao sistema operacional e continuar executando até concluir o objetivo.

## Estado verificável agora

O `main` contém o MVP 0.3 com três processos separados:

- **Painel do Robô** — `127.0.0.1:8765`;
- **Central** — `127.0.0.1:8000`;
- **Robô local** — polling autenticado, planejamento, execução, verificação e telemetria.

Painel e Central continuam locais por padrão. Publicação remota ainda não foi implementada.

## Capacidades já validadas fisicamente

No Linux/X11 real já foram validados:

- ligar, parar e reiniciar Central e Robô pelo Painel;
- parada de emergência persistente e liberação consciente;
- FAILSAFE explícito nos cantos da tela;
- screenshot;
- movimento e clique de mouse;
- abertura de aplicativos;
- digitação Unicode e tecla Enter;
- proteção de foco entre ações de teclado;
- telemetria real de Painel, Central e Robô;
- planner multi-provider com fallback;
- sequência local `abrir editor + escrever` sem provider externo;
- navegação genérica `abrir navegador + acessar site` sem provider externo;
- navegação com navegador específico `abrir Brave + acessar site` sem provider externo;
- sequência local `Brave + Google + pesquisar` sem provider externo.

## Providers

O modo `multi` possui adaptadores para:

- **Z.AI / GLM**;
- **Google Gemini** via SDK oficial `google-genai`;
- **Cloudflare Workers AI**, ainda sem `Account ID` configurado no ambiente real.

Estado observado nos testes recentes:

- Z.AI pode retornar `429/1305` ou resposta sem JSON válido;
- Gemini retornou `429 RESOURCE_EXHAUSTED` por quota;
- tarefas determinísticas conhecidas não devem depender desses providers.

## Testes físicos já relevantes para o novo runtime

### `Abra o editor de texto e escreva Olá mundo` — PASS

- Xed abriu;
- foco correto;
- `Olá mundo` apareceu exatamente;
- task `succeeded`;
- rota local determinística;
- nenhum provider externo necessário.

### Objetivo multi-etapa com leitura de resultado — FALSO PASS histórico

Pedido:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

O Painel marcou `succeeded`, mas fisicamente apenas a pesquisa foi aberta com parte indevida do pedido embutida na consulta. O primeiro resultado não foi lido, o editor não foi aberto e o título não foi escrito.

Esse caso é a regressão principal do Goal Runtime universal.

## Baseline físico de autonomia — conclusão

O executor físico e os fast paths já realizam ações úteis. Os principais FAILs atuais estão em:

- interpretação de intenção natural;
- resolução de capacidades/aplicativos;
- contexto entre tarefas;
- percepção de conteúdo;
- condicionais/replanejamento;
- falso `succeeded` em objetivos compostos.

Não é correto resolver autonomia adicionando regex por frase como estratégia principal.

## Decisão arquitetural vigente — Goal Runtime universal

A direção adotada é um **Goal Runtime universal em ciclo fechado**:

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

Ela já define:

- `GoalContract`;
- `GoalCriterion`;
- `GoalSubgoal`;
- `GoalRunState`;
- `EvidenceRecord`;
- `EvidenceKind`;
- `GoalVerdict`;
- `GoalVerifier`.

Semântica já travada na fundação:

- `ExecutionReceipt` pode registrar que uma ação ocorreu, mas não prova sozinho um efeito do objetivo;
- observação/readback verificado pode satisfazer um critério;
- um critério obrigatório pendente mantém o Goal Run aberto;
- apenas quando todos os critérios obrigatórios possuem prova válida o verifier produz `SUCCEEDED`.

Foi criado `tests/test_goal_runtime_contract.py` com quatro regressões de contrato cobrindo esses pontos.

Antes de publicar os arquivos, a sintaxe foi compilada e quatro checks equivalentes foram executados isoladamente com sucesso. A suíte completa do repositório ainda precisa ser executada pelo CI/local após a integração no `main`.

## O que não foi alterado ainda

A fundação nova não substitui nem intercepta ainda:

- `local_agent.py`;
- planner atual;
- fast paths atuais;
- execução física;
- persistência final da Central.

Isso é intencional para deixar o MVP estável enquanto a integração pesada é feita na próxima etapa.

## Próxima fronteira pesada

A próxima mudança é migrar `local_agent` para que todo pedido crie/use o mesmo Goal Run, convertendo fast paths e planner por IA em fontes de steps, e fazendo o Goal Verifier ser a única autoridade de conclusão.

Depois vêm percepção estruturada, capability resolver, Session Context e Recovery Manager.

## Controles que permanecem

- parada de emergência persistente;
- FAILSAFE físico próprio nos quatro cantos;
- proteção de foco antes de teclado;
- `shell=False`;
- credenciais fora de código, Git, logs e prompts;
- Painel e Central em localhost por padrão.
