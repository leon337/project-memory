# ARCHITECTURE

## Terminologia

- **Painel do Robô** = interface local de operação, configuração, diagnóstico e aprendizado;
- **Central** = processo técnico `Control Plane`;
- **Robô local** = processo técnico `local agent`.

## Arquitetura vigente

```text
Usuário
  ↓
Painel do Robô — FastAPI :8765
  ↓
Central — FastAPI :8000
  ↓
SQLite — fila, histórico e leases
  ↓
HTTP polling autenticado
  ↓
Robô local
  ↓
Goal Runtime universal
  ├─ Goal Contract
  ├─ estado operacional / blackboard
  ├─ subobjetivos e dependências
  ├─ artefatos produzidos
  ├─ Evidence Ledger
  └─ budgets/tentativas
  ↓
Resolução da próxima etapa
  ├─ fast path / skill determinística quando inequívoco
  └─ MultiProviderPlanner quando há semântica, condição, ambiguidade ou replanejamento
       ├─ Cloudflare Workers AI
       ├─ Z.AI / GLM
       └─ Google Gemini
  ↓
Plan / StructuredAction
  ↓
Policy Layer local permissiva por padrão
  ↓
Executores
  ├─ Playwright / Chromium
  └─ Desktop Linux / PyAutoGUI / subprocess
  ↓
Execution Receipt
  ↓
Observação / percepção
  ↓
Evidência
  ↓
Goal Verifier
  ├─ critérios completos → succeeded
  └─ critérios pendentes → replanejar / continuar
```

A implementação completa desse Goal Runtime ainda está em andamento; a arquitetura anterior continua executando o MVP enquanto a migração incremental é feita. Painel, Central e Robô permanecem processos separados.

## 1. Painel do Robô

Implementado em `src/context_anchor/dashboard.py`, bind padrão `127.0.0.1:8765`.

Mostra estado, controles, tarefas recentes, diagnóstico e telemetria real.

## 2. Central

Implementada em `src/context_anchor/control_plane.py`, bind padrão `127.0.0.1:8000`.

Responsável por autenticação separada, persistência, fila, leases e recepção de resultados.

Fluxo persistido:

```text
queued
→ claim + lease
→ running
→ succeeded | failed
```

A Central continua responsável por persistir o verdict final, mas a direção arquitetural é que `succeeded` represente um verdict estruturado de objetivo, não simplesmente o sucesso técnico de uma ação.

## 3. Robô local

Implementado em `src/context_anchor/local_agent.py`.

Responsabilidades atuais:

1. verificar parada de emergência;
2. registrar identidade do processo;
3. buscar tarefa;
4. tentar um caminho local conhecido antes de consumir API externa;
5. obter uma ou mais ações;
6. validar cada ação na Policy Layer;
7. executar;
8. observar/verificar;
9. para objetivos por IA, devolver objetivo + histórico ao planner e continuar até `finish`;
10. enviar resultado à Central e registrar telemetria.

Responsabilidade alvo durante a migração:

- todo pedido cria/usa um Goal Run;
- fast paths passam a produzir etapas dentro desse runtime;
- nenhuma rota possui autoridade paralela para declarar `succeeded`;
- o Goal Verifier fecha o objetivo com base em critérios e evidências.

`CONTEXT_ANCHOR_GOAL_MAX_STEPS` limita as etapas físicas do loop por IA; padrão atual: 8.

## 4. Goal Runtime universal

A unidade cognitiva principal passa a ser o objetivo acompanhado de critérios e evidências.

Contrato mínimo inicial:

- objetivo original;
- subobjetivos necessários;
- critérios de conclusão;
- artefatos produzidos durante a execução;
- evidências coletadas;
- estado de progresso.

O runtime inicial permanece dentro do processo do Robô local. Não criar microserviços para Goal Interpreter, Verifier, Evidence Ledger ou Recovery Manager.

### 4.1 Princípio de fechamento

Nenhum planner, executor ou fast path deve ser considerado autoridade final de sucesso.

Separação conceitual:

```text
Planner       → propõe próxima etapa
Executor      → informa o que executou
Perception    → informa o que observou
Evidence      → liga observação a um critério
Goal Verifier → decide se todos os critérios obrigatórios foram comprovados
```

### 4.2 Fast paths

Fast paths continuam desejáveis para preservar quota e latência, porém passam a ser skills/otimizações dentro do mesmo Goal Run.

Exemplo:

```text
Abra o editor de texto e escreva Olá mundo
```

pode continuar sendo resolvido localmente, mas o objetivo lógico continua contendo, no mínimo:

- editor/superfície de edição disponível;
- texto esperado produzido;
- evidência suficiente para o fechamento.

### 4.3 Execução e evidência

O retorno de uma ação representa um `Execution Receipt`: prova de que a ação foi enviada/executada tecnicamente.

Esse recibo não equivale automaticamente à evidência do objetivo.

Exemplo:

```text
type_text("Olá mundo")
```

pode informar que a entrada foi enviada à janela esperada. A comprovação final de que o conteúdo existe deve vir de observação/readback quando a percepção correspondente estiver disponível.

## 5. Caminho local determinístico

O caminho local reduz latência e consumo de quota quando a intenção já é inequívoca.

### 5.1 Comandos simples

`DeterministicPlanner` resolve comandos conhecidos sem API externa.

Para `abrir/abra/abre ...`:

- alvo que parece URL/domínio → `open_url`;
- outro alvo → `open_app`.

### 5.2 Navegador + site

Construções do tipo `abrir navegador + acessar site` também são resolvidas localmente.

Quando nenhum navegador específico é nomeado, `open_url` usa Playwright/Chromium. Quando um navegador específico é nomeado, ele é preservado e recebe a URL como argumento.

### 5.3 Pesquisa simples

Pedidos inequívocos de pesquisa também ficam no caminho local e viram `open_url` para uma URL de pesquisa conhecida, sem provider externo.

### 5.4 Navegador + mecanismo de busca + consulta

Mecanismos atualmente reconhecidos:

- Google;
- DuckDuckGo;
- Bing.

O parser só usa esse atalho quando conhece a semântica de pesquisa do domínio.

### 5.5 Aplicativo + texto

`plan_local_sequence(...)` reconhece o padrão `abrir aplicativo + escrever/digitar texto`.

A lista de padrões locais deve crescer somente para sequências realmente determinísticas. Ambiguidade, condição ou decisão continuam pertencendo ao raciocínio semântico.

## 6. MultiProviderPlanner

Implementado em `src/context_anchor/planner.py`.

Rotas iniciais:

```text
fast:      Cloudflare → Z.AI → Gemini
reasoning: Z.AI → Gemini → Cloudflare
```

O router considera função da tarefa, saúde recente, cooldown, RPM local e latência. Falha de provider antes da execução pode acionar outro provider.

Providers passam a ser serviços de raciocínio intercambiáveis do Goal Runtime, não uma arquitetura paralela de conclusão.

## 7. Loop orientado a objetivo por IA — legado em migração

O loop atualmente implementado para pedidos por IA continua:

```text
objetivo original
→ próxima StructuredAction
→ política
→ execução
→ observação compacta
→ nova decisão da IA
→ ...
→ finish
```

Durante a migração, `finish` deixa de ser a autoridade arquitetural de sucesso. O planner poderá indicar que acredita não haver mais trabalho, mas o Goal Verifier será responsável pelo verdict final.

## 8. StructuredAction

Ações implementadas atualmente:

- `open_url`;
- `capture_screen`;
- `active_window`;
- `move_mouse`;
- `click_mouse`;
- `type_text`;
- `press_key`;
- `open_app`;
- `finish` — interna ao loop por IA atual.

Campos extras são recusados pelo modelo Pydantic/schema.

## 9. Política local permissiva por padrão

Implementada em `src/context_anchor/policy.py`.

A ausência de cadastro prévio não é motivo suficiente para negar uma ação que o perfil local e o sistema operacional conseguem executar.

Bloqueios específicos futuros entram como denylist ou regras explícitas.

## 10. Resolução de capacidades e aplicativos

Backend físico atual em `src/context_anchor/desktop.py`.

`APP_COMMANDS` e `APP_ALIASES` continuam úteis como hints/resolvedores, não como fronteira de autorização.

A evolução alvo separa:

```text
necessidade do objetivo
→ capability
→ provider local dessa capability
→ aplicativo/executor
```

Exemplos de capabilities genéricas futuras:

- `text.edit`;
- `calculate`;
- `browser.navigate`;
- `browser.search`;
- `browser.read`;
- `desktop.observe`.

Descoberta dinâmica de aplicativos por PATH, `.desktop`, MIME e metadados virá depois da base do Goal Runtime.

## 11. Browser e percepção

`open_url` usa Playwright/Chromium em `src/context_anchor/actions.py`.

A evolução de percepção prioriza fonte estruturada antes de visão:

1. URL/status/título;
2. DOM e texto útil;
3. links/headings/inputs/tabelas;
4. accessibility/ARIA;
5. extração semântica;
6. screenshot;
7. visão multimodal como fallback.

## 12. Desktop, Unicode, foco e FAILSAFE

O desktop físico usa PyAutoGUI no Linux/X11.

Digitação Unicode, proteção de foco e FAILSAFE próprio de 20 pixels nos quatro cantos permanecem inalterados durante a migração cognitiva.

## 13. Emergency stop

`src/context_anchor/emergency_stop.py` usa sentinel persistente, PID + identidade Linux e bloqueio de reinício até liberação consciente.

Permanece independente do planner e dos providers.

## 14. Providers

### Z.AI

- modelo padrão `glm-4.7-flash`;
- HTTP por `httpx`;
- JSON estruturado;
- testes reais podem retornar `429/1305` ou resposta sem JSON válido.

### Gemini

- SDK oficial `google-genai`;
- `client.models.generate_content(...)`;
- modelo padrão `gemini-3.6-flash`;
- `response_json_schema=ACTION_SCHEMA`;
- `max_output_tokens=1024`;
- saída revalidada como `StructuredAction`;
- nos testes recentes retornou `429 RESOURCE_EXHAUSTED` por quota.

### Cloudflare Workers AI

Adaptador implementado, mas o ambiente real ainda precisa do `Account ID` para entrar no router.

## 15. Credenciais e telemetria

Credenciais permanecem fora de código, Git, prompts e logs.

Telemetria real por componente:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

## 16. Contexto operacional

Ainda não existe memória operacional explícita entre tasks independentes.

A evolução prevista é manter um `Session Context` curto e tipado, com referências como último assunto, browser/session, site, editor/documento e artefatos recentes, sem transformar histórico bruto em memória.

## 17. Acesso remoto

Painel e Central continuam localhost. Publicação remota ainda não foi implementada.

Canais futuros continuam Web remoto, WhatsApp, Telegram e Instagram.

## 18. Estado de validação

Já existem PASS físicos para editor + escrita, navegador + site e outras sequências locais.

O baseline de autonomia também comprovou FAILs de interpretação geral, resolução de capacidades, contexto, condicionais e um falso `succeeded` em objetivo composto. Esses FAILs são a base de regressão para o Goal Runtime universal.
