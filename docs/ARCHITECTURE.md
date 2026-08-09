# ARCHITECTURE

## Terminologia usada

- **Painel do Robô** = gerenciador local de operação, configuração, diagnóstico e aprendizado;
- **Central** = processo técnico `Control Plane`;
- **Robô local** = processo técnico `local agent`.

## Arquitetura implementada no MVP 0.3

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
Planner
  ├─ DeterministicPlanner
  └─ MultiProviderPlanner
       ├─ Cloudflare Workers AI
       ├─ Z.AI / GLM
       └─ Google Gemini
  ↓
StructuredAction
  ↓
Policy Layer
  ├─ navegador
  └─ desktop + feature gate
  ↓
Executores
  ├─ Playwright / Chromium
  └─ PyAutoGUI / Linux X11
  ↓
Verificação
  ↓
Central / Painel do Robô
```

Painel, Central e Robô são processos separados para que o Painel continue disponível mesmo quando Central ou Robô forem reiniciados.

## 1. Painel do Robô

Implementado em `src/context_anchor/dashboard.py`, bind padrão `127.0.0.1:8765`.

Mostra estado, controles, tarefas recentes, diagnóstico e telemetria real. Não possui endpoint de shell arbitrário.

## 2. Central

Implementada em `src/context_anchor/control_plane.py`, bind padrão `127.0.0.1:8000`.

Responsável por autenticação separada, persistência, fila, leases e recepção de resultados.

## 3. Persistência e leases

Implementada em `src/context_anchor/store.py` com SQLite.

```text
queued
  ↓ claim + lease
running
  ↓
succeeded | failed
```

Resultado atrasado com lease antigo é rejeitado e tarefa abandonada pode retornar à fila dentro do limite de tentativas.

## 4. Robô local

Implementado em `src/context_anchor/local_agent.py`.

Fluxo:

1. verifica emergência;
2. registra identidade do processo;
3. autentica na Central;
4. busca tarefa;
5. obtém plano;
6. valida na Policy Layer;
7. executa;
8. verifica;
9. envia resultado;
10. registra telemetria.

`build_planner()` escolhe o modo conforme `CONTEXT_ANCHOR_PLANNER_MODE`.

## 5. Planner determinístico

`DeterministicPlanner` permanece em `src/context_anchor/planner.py` e continua sendo o modo padrão.

Mesmo quando o modo multi-provider estiver ativo, o roteador tenta primeiro o planner determinístico. Se o pedido já pertence ao vocabulário conhecido, nenhuma API externa é chamada.

Isso preserva compatibilidade, reduz latência e economiza quota.

## 6. MultiProviderPlanner

Implementado em `src/context_anchor/planner.py`.

A primeira versão classifica pedidos de texto em duas rotas:

- `fast` — pedidos simples;
- `reasoning` — pedidos mais longos ou com marcadores de análise, condição, comparação e decisão.

Ordem inicial:

```text
fast:
Cloudflare → Z.AI → Gemini

reasoning:
Z.AI → Gemini → Cloudflare
```

O roteador mantém por provedor:

- sucessos;
- falhas;
- falhas consecutivas;
- última latência observada;
- `cooldown_until`;
- timestamps locais de requests para aplicar um teto RPM quando configurado.

Uma falha de rede, 429, resposta inválida ou `StructuredAction` inválida ocorre antes de a execução física receber um `Plan`; por isso outro provedor pode ser tentado nessa etapa sem repetir clique, digitação ou outra ação já executada.

O roteador não é round-robin.

## 7. Adaptadores de IA

Implementados em `src/context_anchor/providers.py` usando `httpx`, que já fazia parte das dependências do projeto.

### 7.1 Z.AI

- endpoint geral de chat completions;
- modelo padrão: `glm-4.7-flash`;
- autenticação Bearer;
- `response_format={"type":"json_object"}`;
- resposta convertida e validada como `StructuredAction`.

### 7.2 Cloudflare Workers AI

- REST API de Workers AI por `Account ID`;
- modelo padrão do fast planner: `@cf/meta/llama-3.1-8b-instruct-fast`;
- autenticação Bearer por token Workers AI;
- usa `response_format` com JSON Schema do contrato de ação;
- RPM local configurável, inicialmente 300.

### 7.3 Gemini

- REST `generateContent`;
- modelo padrão: `gemini-3.5-flash`;
- autenticação por `x-goog-api-key`;
- usa structured response format com o mesmo JSON Schema;
- RPM local configurável, inicialmente 20.

O adaptador Gemini desta etapa é textual. Visão/multimodalidade ainda não foi ligada ao router.

## 8. Contrato StructuredAction

A IA só pode propor uma das ações conhecidas:

- `open_url`;
- `capture_screen`;
- `active_window`;
- `move_mouse`;
- `click_mouse`;
- `type_text`;
- `press_key`;
- `open_app`.

Campos extras são recusados. Não existe ação de shell, código livre, caminho arbitrário de executável ou credencial.

Uma ação estruturalmente válida ainda precisa passar pela Policy Layer.

## 9. Configuração do planner

`LocalAgentSettings` aceita:

```text
CONTEXT_ANCHOR_PLANNER_MODE
CONTEXT_ANCHOR_PLANNER_TIMEOUT_SECONDS
CONTEXT_ANCHOR_PLANNER_COOLDOWN_SECONDS

CONTEXT_ANCHOR_ZAI_API_KEY
CONTEXT_ANCHOR_ZAI_MODEL

CONTEXT_ANCHOR_CLOUDFLARE_API_TOKEN
CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID
CONTEXT_ANCHOR_CLOUDFLARE_MODEL
CONTEXT_ANCHOR_CLOUDFLARE_RPM_LIMIT

CONTEXT_ANCHOR_GEMINI_API_KEY
CONTEXT_ANCHOR_GEMINI_MODEL
CONTEXT_ANCHOR_GEMINI_RPM_LIMIT
```

O modo `multi` usa somente provedores com configuração suficiente. Assim, o router pode ser validado primeiro com Z.AI/Gemini e receber Cloudflare depois que o Account ID estiver configurado.

## 10. Credenciais

Credenciais nunca entram em código, Git, logs ou prompts.

`.env.example` contém apenas nomes de variáveis e valores vazios para segredos.

O Robô registra nomes de provedores e rotas, não os tokens.

## 11. Policy Layer

Implementada em `src/context_anchor/policy.py`.

Toda ação, independentemente de qual planner/provedor a gerou, passa pela mesma política.

Navegação bloqueia destinos locais/privados. Desktop permanece atrás de feature gate e allowlists de ação, coordenada, tecla e aplicativo.

## 12. Navegador

Implementado em `src/context_anchor/actions.py` com Playwright/Chromium.

Preferência arquitetural:

```text
API/DOM
→ automação estruturada
→ acessibilidade
→ visão + mouse/teclado como fallback
```

## 13. Desktop e FAILSAFE

Backend em `src/context_anchor/desktop.py`.

Além de `pyautogui.FAILSAFE = True`, uma zona própria de 20 pixels nos quatro cantos interrompe entradas físicas antes de mover, clicar, digitar ou pressionar tecla.

## 14. Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py` com sentinel persistente, PID + identidade Linux e bloqueio de reinício até liberação consciente.

Permanece independente do planner e dos provedores de IA.

## 15. Telemetria

Telemetria estruturada em `src/context_anchor/runtime_log.py`:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Resultados de tarefas planejadas por IA podem incluir nome do provedor, rota e nomes de provedores que falharam, sem segredos.

## 16. Percepção

Primeiro slice implementado: screenshot e janela ativa.

Ainda faltam árvore de acessibilidade, percepção semântica de imagem e integração multimodal ao router.

## 17. Acesso remoto — futuro

Antes de publicar Painel ou Central na Internet serão necessários TLS, autenticação forte, pareamento, revogação, rate limiting, proteção contra replay, auditoria e confirmação para ações sensíveis.

## 18. Canais — futuro

```text
Web remoto
WhatsApp
Telegram
Instagram
    ↓
Gateway de comandos
    ↓
Central
    ↓
Robô local
```

## 19. Princípio local-first

O controle físico permanece no Robô local. Nenhum provedor de IA acessa diretamente mouse, teclado, câmera ou aplicativos; ele apenas propõe uma `StructuredAction`, que continua subordinada à Policy Layer e às proteções locais.
