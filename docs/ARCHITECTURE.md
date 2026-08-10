# ARCHITECTURE

## Terminologia

- **Painel do Robô** = interface local de operação, configuração, diagnóstico e aprendizado;
- **Central** = processo técnico `Control Plane`;
- **Robô local** = processo técnico `local agent`.

## Estado da versão

A arquitetura abaixo é a versão verificada do Goal Runtime. Ela foi validada na branch de recuperação `codex/goal-runtime-wip` e o mesmo SHA é promovido para `main` no encerramento da missão.

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
HTTP polling autenticado + lease heartbeat
  ↓
Robô local
  ↓
Session Context curto
  ↓
SemanticGoalInterpreter
  ├─ intent local tipado quando a cobertura é inequívoca
  └─ GENERIC → decomposição estruturada completa por provider
  ↓
GoalContract + GoalRunState
  ├─ subobjetivos / DAG
  ├─ critérios obrigatórios
  ├─ artefatos/dataflow
  ├─ Evidence Ledger
  └─ budgets / guards / progresso
  ↓
Capability Resolver quando necessário
  ├─ PATH
  ├─ XDG .desktop
  ├─ categorias
  └─ aliases/hints
  ↓
Plan / operação estruturada
  ↓
Policy Layer
  ↓
LeaseGuardedExecutor
  ├─ Playwright / Chromium
  └─ Desktop Linux / subprocess / PyAutoGUI
  ↓
ExecutionReceipt
  ↓
Percepção independente
  ├─ browser DOM/URL/status/resultados
  ├─ X11/processo/WM_CLASS
  └─ AT-SPI/readback
  ↓
EvidenceRecord
  ↓
GoalVerifier
  ├─ critérios + subobjetivos comprovados → succeeded
  └─ pendência/falha → continuar, fallback limitado ou failed
  ↓
Resultado sanitizado
  ↓
ACK da Central
  ↓
commit do contexto entre tasks
```

## 1. Processos preservados

Painel, Central e Robô continuam processos separados.

A fila persiste em SQLite e mantém o ciclo:

```text
queued → running → succeeded | failed
```

`succeeded` só é enviado pelo Robô depois de um verdict comprovado do Goal Runtime.

## 2. Goal Runtime universal

Módulos principais:

- `goal_runtime.py` — contratos, critérios, subobjetivos, evidências, steps, budgets e verifier;
- `goal_execution.py` — orquestração de uma execução completa;
- `local_agent.py` — integra o Goal Runtime ao fluxo real do Robô.

Todo comando entra em `execute_goal()`.

Fast paths e decomposição por provider são fontes diferentes de steps, mas não possuem semânticas diferentes de conclusão.

## 3. Regra de evidência e conclusão

```text
Planner/Interpreter → propõe/decompõe
Executor            → executa
ExecutionReceipt    → comprova somente execução técnica
Perception          → observa efeito
EvidenceRecord      → liga observação a critério
GoalVerifier        → decide conclusão
```

`EvidenceKind.EXECUTION_RECEIPT` nunca satisfaz sozinho um critério final.

O verifier exige todos os critérios obrigatórios e subobjetivos dependentes satisfeitos antes de `SUCCEEDED`.

## 4. Interpretação e cobertura de objetivo

`SemanticGoalInterpreter` reconhece localmente conceitos inequívocos como:

- edição de texto;
- cálculo/ferramenta de cálculo;
- VS Code/code editing;
- busca web;
- pesquisa em navegador nomeado;
- informação/pesquisa+leitura;
- pesquisa→resultado→editor;
- condicional de acessibilidade de site.

A classificação local é fail-closed: um fast path só é aceito quando consegue representar todas as ações/entidades materiais do pedido.

Pedidos `GENERIC` exigem decomposição estruturada completa antes da primeira ação física.

## 5. Grounding e prova em navegador nomeado

Fast path permitido:

- `No Brave, pesquise gatos`;
- `Abra o Brave, acesse google.com e pesquise gatos`;
- equivalentes usando Bing ou DuckDuckGo.

Uma URL explícita não reconhecida como mecanismo de busca, como `example.com`, não pode ser descartada. Esse caso vai para `GENERIC`/fail-closed antes da execução.

Um navegador externo como Brave não compartilha o DOM do Chromium controlado por Playwright. A comprovação usa, cumulativamente:

- XID ativo revalidado antes/depois da leitura;
- `WM_CLASS` exato para o navegador solicitado;
- `_NET_WM_PID` do mesmo XID e executável compatível em `/proc`;
- omnibox obtida por AT-SPI apenas no chrome do navegador, nunca dentro do documento web;
- URL canônica com scheme sem downgrade, host, porta, path e parâmetros solicitados compatíveis;
- `argv` do receipt contendo a URL realmente emitida.

Título de janela é apenas diagnóstico e não participa do verdict. Se a janela já estiver comprovadamente no estado alvo, `window_changed=false` não invalida o objetivo: o pós-estado independente prevalece sobre o receipt técnico.

## 6. Capability Resolver

`capabilities.py` separa necessidade de aplicativo concreto.

Capabilities atuais:

- `text.edit`;
- `calculate`;
- `web.search`;
- `web.read`;
- `browser.navigate`;
- `code.edit`.

A descoberta usa executáveis realmente instalados e metadados XDG. Perfis/aliases são preferências e hints, não uma allowlist absoluta.

Hints explícitos podem operar em modo estrito para impedir trocar silenciosamente o aplicativo pedido.

## 7. Percepção

### Browser

`actions.py` expõe observação estruturada via Playwright, incluindo:

- URL final;
- status HTTP;
- título;
- texto visível;
- resultados estruturados;
- primeiro resultado/título/URL.

Feeds RSS/Atom podem produzir resultados estruturados somente quando o content-type XML e a raiz `rss`/`feed` comprovam que o documento é um feed. Em Atom, `rel=alternate` é preferido e `rel=self` não é tratado como resultado.

### Desktop

`desktop.py` usa:

- processo/PID;
- janela ativa;
- X11/`WM_CLASS`;
- argumentos observáveis quando possível;
- AT-SPI/readback para texto.
- AT-SPI da omnibox para a localização de navegadores externos.

Screenshot continua disponível, mas não é a prova padrão para fluxos que possuem observadores estruturados.

## 8. Dataflow e artefatos

`GoalContract.artifacts` carrega valores produzidos por etapas e consumidos posteriormente.

Exemplo crítico:

```text
pesquisa
→ first_result_title
→ abrir editor
→ escrever ${first_result_title}
→ readback exato
```

Uma etapa estruturada não pode declarar produção de artifact sem realmente materializá-lo.

## 9. Contexto operacional entre tasks

`session_context.py` persiste somente artefatos tipados e limitados:

- subject;
- location;
- site;
- browser;
- editor;
- result.

Possui TTL, limites de tamanho/quantidade, proveniência por task, lock e escrita atômica.

Referências suportadas incluem `lá`, `nesse navegador`, `nesse site`, `nesse editor`, `aquele resultado` e `esse assunto`.

O contexto produzido por uma task só é commitado depois do ACK final da Central.

## 10. Leases e execução física

`lease.py` adiciona heartbeat e `LeaseGuardedExecutor`.

Ações e observações são protegidas contra perda de posse da task. A conclusão da Central também valida o lease vigente.

Ações físicas não idempotentes não são repetidas cegamente após erro/observação inconclusiva.

## 11. Providers

Z.AI, Gemini e Cloudflare continuam como serviços intercambiáveis de raciocínio/decomposição.

Providers não são autoridade de conclusão.

Fast paths locais evitam provider quando a intenção é inequívoca; objetivos `GENERIC` dependem de decomposição estruturada por provider disponível.

## 12. Recovery e budgets

`GoalRunState` limita:

- número de steps;
- retries por estratégia;
- repetições;
- passos sem progresso.

Buscas possuem fallback limitado entre mecanismos HTML e, como última alternativa, um feed Bing RSS estruturado. O replanning estruturado após toda falha física ainda é limitado e permanece área de evolução posterior.

## 13. Privacidade e telemetria

`redaction.py` sanitiza resultados/logs/contexto e remove padrões sensíveis. Conteúdo digitado não é persistido integralmente em evidências públicas.

## 14. Controles preservados

Permanecem obrigatórios:

- Policy Layer;
- `shell=False`;
- foco observável;
- FAILSAFE dos quatro cantos;
- Emergency Stop persistente;
- credenciais fora do Git/logs/prompts;
- localhost por padrão.

## 15. Gate de release cumprido

A versão foi fechada somente depois de:

- bateria física integrada A–E pelo fluxo real Painel → Central → Robô;
- 11 registros finais com uma tentativa, critérios/subobjetivos completos e evidência independente;
- correção e repetição das falhas reais encontradas;
- suíte completa com 351 testes verdes;
- compilação de 48 arquivos Python;
- `git diff --check` e revisão independente do diff;
- atualização coordenada dos quatro documentos de memória.
