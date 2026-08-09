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
Planner
  ├─ DeterministicPlanner
  └─ MultiProviderPlanner
       ├─ Cloudflare Workers AI
       ├─ Z.AI / GLM
       └─ Google Gemini
  ↓
StructuredAction — uma próxima ação por decisão
  ↓
Policy Layer local permissiva por padrão
  ↓
Executores
  ├─ Playwright / Chromium
  └─ Desktop Linux / PyAutoGUI / subprocess
  ↓
Observação e verificação
  ↓
Objetivo concluído?
  ├─ não → volta ao Planner com histórico
  └─ sim → action=finish → resultado para Central/Painel
```

Painel, Central e Robô permanecem processos separados para que o Painel continue disponível quando Central ou Robô forem reiniciados.

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

## 3. Robô local

Implementado em `src/context_anchor/local_agent.py`.

Responsabilidades:

1. verificar parada de emergência;
2. registrar identidade do processo;
3. buscar tarefa;
4. obter a próxima ação;
5. validar a ação na Policy Layer;
6. executar;
7. observar/verificar o resultado;
8. quando o pedido veio da IA, devolver objetivo + histórico ao planner;
9. repetir até `finish`, falha ou limite de etapas;
10. enviar resultado à Central e registrar telemetria.

`CONTEXT_ANCHOR_GOAL_MAX_STEPS` limita o número de etapas físicas do loop; padrão atual: 8.

## 4. Planner determinístico

`DeterministicPlanner` continua como caminho local rápido e sem custo de API.

Ele resolve somente comandos inequívocos do vocabulário conhecido. O parser de `abrir ...` só assume URL quando o alvo se parece de fato com URL/domínio. Frases como `abrir o navegador brave` não são convertidas em URL e podem seguir para o planner de IA.

Pedidos determinísticos simples continuam com execução única.

## 5. MultiProviderPlanner

Implementado em `src/context_anchor/planner.py`.

Rotas iniciais:

```text
fast:      Cloudflare → Z.AI → Gemini
reasoning: Z.AI → Gemini → Cloudflare
```

O router considera função da tarefa, saúde recente, cooldown, RPM local e latência. Falha de provider antes da execução pode acionar outro provider.

O fallback nunca deve repetir automaticamente uma ação física que já foi executada.

## 6. Loop orientado a objetivo

Para pedidos planejados por IA, o sistema não trata mais a primeira ação bem-sucedida como conclusão automática do objetivo.

O contrato é:

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

A IA recebe o objetivo original e um histórico compacto das etapas já executadas. O histórico inclui somente dados operacionais necessários, como ação, alvo, janela, URL, coordenadas e `verified`.

Se uma etapa retornar `verified=False`, o loop falha em vez de marcar o objetivo como concluído.

`finish` é uma ação interna: ela não é enviada ao executor físico. Só encerra uma tarefa depois de existir ao menos uma etapa executada.

## 7. StructuredAction

O provider continua produzindo uma ação por decisão, não uma lista inteira antecipadamente.

Ações implementadas atualmente:

- `open_url`;
- `capture_screen`;
- `active_window`;
- `move_mouse`;
- `click_mouse`;
- `type_text`;
- `press_key`;
- `open_app`;
- `finish` — interna ao loop.

Campos extras são recusados pelo modelo Pydantic/schema.

## 8. Política local permissiva por padrão

Implementada em `src/context_anchor/policy.py`.

A direção vigente é permitir por padrão o que o perfil local e o sistema operacional conseguem executar. A ausência de cadastro prévio não é motivo suficiente para negar uma ação.

Atualmente:

- `open_app` não depende de `SUPPORTED_APP_IDS` para autorização;
- URLs HTTP/HTTPS públicas, privadas ou locais são aceitas pela política local;
- nomes de tecla imprimíveis não dependem de uma lista fechada;
- ações ainda sem executor implementado continuam falhando por ausência de implementação, não por allowlist.

Bloqueios específicos futuros devem entrar como denylist ou regras explícitas escolhidas pelo usuário.

## 9. Resolução de aplicativos e processos

Backend em `src/context_anchor/desktop.py`.

`APP_COMMANDS` e `APP_ALIASES` permanecem como resolvedores convenientes para nomes comuns; não são mais fronteira de autorização.

Para `open_app`, o backend tenta:

1. aliases/candidatos conhecidos;
2. executável/comando informado diretamente;
3. variações simples de nome quando aplicável.

Argumentos são separados por `shlex.split(...)` e o processo atual usa `subprocess.Popen(..., shell=False)`.

Brave possui aliases de conveniência para `brave-browser`, `brave-browser-stable` e `brave`.

Se o executável não existir na sessão do usuário, a falha correta é `FileNotFoundError`, não `PermissionError` de allowlist.

## 10. Browser

`open_url` é executado por Playwright/Chromium em `src/context_anchor/actions.py`.

Abrir um navegador instalado como aplicativo é diferente de navegar para uma URL: o primeiro usa `open_app`, o segundo usa `open_url`.

## 11. Desktop, foco e FAILSAFE

O desktop físico usa PyAutoGUI no Linux/X11.

Além do `pyautogui.FAILSAFE`, o backend verifica uma zona própria de 20 pixels nos quatro cantos antes de entrada física.

Ao abrir um aplicativo ou clicar, a janela observada pode se tornar o foco esperado. Antes de `type_text` e `press_key`, uma mudança de janela observável é recusada para evitar digitar no lugar errado.

Essa proteção de foco é independente de allowlist de aplicativos.

## 12. Emergency stop

`src/context_anchor/emergency_stop.py` usa sentinel persistente, PID + identidade Linux e bloqueio de reinício até liberação consciente.

Permanece independente do planner e dos providers.

## 13. Providers

### Z.AI

- modelo padrão `glm-4.7-flash`;
- HTTP por `httpx`;
- JSON estruturado;
- testes reais podem retornar `429/1305`.

### Gemini

- SDK oficial `google-genai`;
- `client.models.generate_content(...)`;
- modelo padrão `gemini-3.6-flash`;
- `response_json_schema=ACTION_SCHEMA`;
- `max_output_tokens=1024`;
- saída sempre revalidada como `StructuredAction`.

### Cloudflare Workers AI

Adaptador implementado, mas o ambiente real ainda precisa do `Account ID` para entrar no router.

## 14. Configuração relevante

```text
CONTEXT_ANCHOR_PLANNER_MODE
CONTEXT_ANCHOR_PLANNER_TIMEOUT_SECONDS
CONTEXT_ANCHOR_PLANNER_COOLDOWN_SECONDS
CONTEXT_ANCHOR_GOAL_MAX_STEPS

CONTEXT_ANCHOR_ZAI_API_KEY
CONTEXT_ANCHOR_ZAI_MODEL

CONTEXT_ANCHOR_GEMINI_API_KEY
CONTEXT_ANCHOR_GEMINI_MODEL
CONTEXT_ANCHOR_GEMINI_RPM_LIMIT

CONTEXT_ANCHOR_CLOUDFLARE_API_TOKEN
CONTEXT_ANCHOR_CLOUDFLARE_ACCOUNT_ID
CONTEXT_ANCHOR_CLOUDFLARE_MODEL
CONTEXT_ANCHOR_CLOUDFLARE_RPM_LIMIT
```

## 15. Credenciais e telemetria

Credenciais permanecem fora de código, Git, prompts e logs.

Telemetria real por componente:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

O resultado de uma tarefa de objetivo pode incluir etapas, provider, rota e fallbacks sem incluir tokens.

## 16. Percepção atual

Já existem screenshot e janela ativa.

Ainda não existem árvore de acessibilidade, percepção semântica de screenshots nem visão multimodal integrada ao loop.

## 17. Acesso remoto

Painel e Central continuam localhost. Publicação remota exige uma camada separada de autenticação/transporte e ainda não foi implementada.

Canais futuros continuam Web remoto, WhatsApp, Telegram e Instagram.

## 18. Estado de validação

A primeira ação IA → Xed foi validada fisicamente antes do loop.

A política permissiva, o resolvedor genérico e o loop `open_app → type_text → finish` passaram em testes automatizados e CI, mas **ainda precisam de validação física no Linux real**.
