# ARCHITECTURE

## Terminologia

- **Painel do Robô** = interface local de operação, configuração, diagnóstico e aprendizado;
- **Central** = processo técnico `Control Plane`;
- **Robô local** = processo técnico `local agent`.

## Arquitetura vigente e direção de migração

O MVP continua operacional com Painel, Central e Robô separados. A nova fundação cognitiva está sendo introduzida incrementalmente sem substituir de uma vez o fluxo físico já validado.

Arquitetura alvo:

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
EvidenceRecord
  ↓
Goal Verifier
  ├─ critérios completos → succeeded
  └─ critérios pendentes → replanejar / continuar
```

## 1. Processos existentes que permanecem

### Painel

`src/context_anchor/dashboard.py`, bind padrão `127.0.0.1:8765`.

### Central

`src/context_anchor/control_plane.py`, bind padrão `127.0.0.1:8000`.

Fluxo persistido atual:

```text
queued → running → succeeded | failed
```

A direção é que o `succeeded` final passe a representar um verdict estruturado de objetivo, não simplesmente o retorno positivo de uma ação.

### Robô local

`src/context_anchor/local_agent.py` continua sendo o processo coordenador físico. A refatoração pesada para tornar o Goal Runtime universal ainda não foi feita.

## 2. Fundação do Goal Runtime — implementada isoladamente

Novo módulo:

`src/context_anchor/goal_runtime.py`

Contratos existentes:

- `GoalContract` — objetivo original, critérios, subobjetivos e artefatos;
- `GoalCriterion` — efeito obrigatório/opcional a comprovar;
- `GoalSubgoal` — unidade de progresso e dependências;
- `GoalRunState` — estado vivo de uma execução;
- `EvidenceRecord` — evidência ligada a um critério;
- `EvidenceKind` — diferencia receipt, observação, readback e assertion;
- `GoalVerdict` — resultado do verifier;
- `GoalVerifier` — autoridade determinística mínima de conclusão.

Essa fundação ainda não intercepta o `local_agent` atual.

## 3. Regra fundamental de evidência

A arquitetura separa quatro conceitos:

```text
Planner       → propõe próxima etapa
Executor      → produz Execution Receipt
Perception    → observa estado real
Evidence      → relaciona observação ao critério
Goal Verifier → decide conclusão
```

`EvidenceKind.EXECUTION_RECEIPT` nunca prova sozinho um efeito do objetivo, mesmo quando o executor informa sucesso técnico.

Observação/readback marcada como verificada pode satisfazer um critério. Todos os critérios obrigatórios precisam de prova antes de `GoalVerifier` produzir `SUCCEEDED`.

Isso trava em código a distinção entre:

```text
ação executada ≠ objetivo concluído
```

## 4. Fast paths

Fast paths determinísticos continuam desejáveis para preservar quota e latência.

Na arquitetura alvo eles deixam de possuir uma semântica paralela de conclusão e passam a funcionar como skills/otimizações dentro do Goal Run.

Exemplo:

```text
Abra o editor de texto e escreva Olá mundo
```

pode continuar usando duas ações locais, mas o Goal Contract deve representar os efeitos finais e o verifier deve fechar o objetivo.

## 5. MultiProviderPlanner

`src/context_anchor/planner.py` continua com Z.AI, Gemini e Cloudflare como serviços de raciocínio intercambiáveis.

Providers não são autoridade de conclusão. O planner pode sugerir uma próxima ação ou indicar que acredita não haver mais trabalho; o Goal Verifier continua responsável pelo verdict.

## 6. StructuredAction

As ações físicas tipadas atuais permanecem como nível de executor. Não transformar o Goal Contract em comandos de mouse/clique.

Ações atualmente existentes incluem navegação, captura, janela ativa, mouse, teclado, aplicativo e `finish` legado do loop por IA.

Durante a migração, `finish` deixa de ser autoridade final e passa no máximo a ser um sinal do planner para o verifier avaliar o estado.

## 7. Policy Layer e perfil local

A Policy Layer permanece antes do executor e o perfil local continua permissivo por padrão, com bloqueios futuros por exceção.

FAILSAFE, proteção de foco e Emergency Stop permanecem fora do raciocínio e não devem ser enfraquecidos pela migração.

## 8. Resolução de capacidades — próxima camada depois do runtime

A abstração alvo é:

```text
necessidade do objetivo
→ capability
→ provider local dessa capability
→ aplicativo/executor
```

Exemplos futuros:

- `text.edit`;
- `calculate`;
- `browser.navigate`;
- `browser.search`;
- `browser.read`;
- `desktop.observe`.

Aliases continuam como hints/cache, não como mecanismo principal de inteligência.

## 9. Percepção

Prioridade de percepção no browser:

1. URL/status/título;
2. DOM/texto útil;
3. links/headings/inputs/tabelas;
4. accessibility/ARIA;
5. extração semântica;
6. screenshot;
7. visão multimodal como fallback.

No desktop Linux/X11:

1. janela/processo;
2. accessibility/AT-SPI;
3. árvore compacta da UI;
4. screenshot;
5. OCR/visão como fallback.

## 10. Contexto operacional futuro

Session Context curto e tipado para referências entre tasks, como último assunto, browser/session, site, editor/documento e artefatos recentes.

Não usar histórico bruto como memória operacional.

## 11. Recovery futuro

Recovery Manager deve trabalhar com falhas tipadas, budgets, detector de falta de progresso e estratégias alternativas, evitando repetir indefinidamente o mesmo estado/ação.

## 12. Controles preservados

Durante toda a migração permanecem:

- processos Painel/Central/Robô separados;
- SQLite + leases;
- Policy Layer;
- executores atuais;
- `shell=False`;
- foco observável;
- FAILSAFE dos quatro cantos;
- Emergency Stop persistente;
- credenciais fora de código/prompts/logs;
- localhost por padrão.
