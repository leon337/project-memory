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
Interpretação do objetivo
  ├─ caminho local conhecido
  │    ├─ comando determinístico simples
  │    ├─ navegação/pesquisa web determinística
  │    └─ sequência determinística composta
  └─ MultiProviderPlanner
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
Observação e verificação
  ↓
Objetivo concluído?
  ├─ sequência local conhecida: termina quando todas as etapas verificam
  └─ objetivo por IA: volta ao planner até action=finish
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
4. tentar um caminho local conhecido antes de consumir API externa;
5. obter uma ou mais ações;
6. validar cada ação na Policy Layer;
7. executar;
8. observar/verificar;
9. para objetivos por IA, devolver objetivo + histórico ao planner e continuar até `finish`;
10. enviar resultado à Central e registrar telemetria.

`CONTEXT_ANCHOR_GOAL_MAX_STEPS` limita as etapas físicas do loop por IA; padrão atual: 8.

## 4. Caminho local determinístico

O caminho local reduz latência e consumo de quota quando a intenção já é inequívoca.

### 4.1 Comandos simples

`DeterministicPlanner` resolve comandos conhecidos sem API externa.

Para `abrir/abra/abre ...`:

- alvo que parece URL/domínio → `open_url`;
- outro alvo → `open_app`.

Exemplo:

```text
abrir o navegador brave
→ open_app(brave-browser)
```

### 4.2 Navegador + site

Construções do tipo `abrir navegador + acessar site` também são resolvidas localmente.

Exemplos:

```text
abrir o navegador e acessar globo.com
→ open_url(https://globo.com)
```

```text
Abra o navegador brave e acesse google.com
→ open_app("brave-browser https://google.com")
```

Quando nenhum navegador específico é nomeado, `open_url` usa Playwright/Chromium. Quando um navegador específico é nomeado, ele é preservado e recebe a URL como argumento.

### 4.3 Pesquisa simples

Pedidos inequívocos de pesquisa também ficam no caminho local.

Exemplos aceitos:

```text
pesquise inteligência artificial
agora pesquise sobre inteligência artificial
busque FastAPI
procure agentes de IA
```

Esses pedidos viram `open_url` para uma URL de pesquisa em DuckDuckGo e não usam provider externo.

O prefixo `agora` não cria, por si só, memória de navegador externo. Neste estágio, `agora pesquise ...` significa uma nova pesquisa web determinística no navegador estruturado.

### 4.4 Navegador + mecanismo de busca + consulta

Para mecanismos conhecidos, o parser pode montar diretamente a URL final da busca.

Mecanismos atualmente reconhecidos:

- Google;
- DuckDuckGo;
- Bing.

Exemplo com navegador específico:

```text
Abra o navegador brave e acesse o site google.com e pesquise o significado do nome Josiel
→ open_app("brave-browser https://www.google.com/search?q=o+significado+do+nome+Josiel")
```

Exemplo com navegador genérico:

```text
Abra o navegador e acesse google.com e pesquise inteligência artificial
→ open_url("https://www.google.com/search?q=intelig%C3%AAncia+artificial")
```

O parser só usa esse atalho quando conhece a semântica de pesquisa do domínio. Sites arbitrários não recebem uma suposição genérica de endpoint de busca.

### 4.5 Aplicativo + texto

`plan_local_sequence(...)` reconhece o padrão:

```text
abrir aplicativo + escrever/digitar texto
```

Exemplo:

```text
Abra o editor de texto e escreva Olá mundo
→ open_app(editor)
→ verificar
→ type_text("Olá mundo")
→ verificar
→ objetivo concluído
```

Essa sequência não chama provider externo.

A lista de padrões locais deve crescer somente para sequências realmente determinísticas. Ambiguidade, condição ou decisão continuam pertencendo ao planner por IA.

## 5. MultiProviderPlanner

Implementado em `src/context_anchor/planner.py`.

Rotas iniciais:

```text
fast:      Cloudflare → Z.AI → Gemini
reasoning: Z.AI → Gemini → Cloudflare
```

O router considera função da tarefa, saúde recente, cooldown, RPM local e latência. Falha de provider antes da execução pode acionar outro provider.

O fallback não deve repetir automaticamente uma ação física que já foi executada.

## 6. Loop orientado a objetivo por IA

Para pedidos que exigem IA:

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

A IA recebe o objetivo original e um histórico compacto das etapas executadas.

Se uma etapa retornar `verified=False`, o loop falha em vez de marcar o objetivo como concluído.

`finish` é interno e não é enviado ao executor físico. Só encerra uma tarefa depois de existir ao menos uma etapa executada.

Esse loop continua necessário para tarefas condicionais, ambíguas ou que dependem de observação intermediária. O caminho local não o substitui; apenas evita chamadas externas quando não há raciocínio real a fazer.

## 7. StructuredAction

Ações implementadas atualmente:

- `open_url`;
- `capture_screen`;
- `active_window`;
- `move_mouse`;
- `click_mouse`;
- `type_text`;
- `press_key`;
- `open_app`;
- `finish` — interna ao loop por IA.

Campos extras são recusados pelo modelo Pydantic/schema.

## 8. Política local permissiva por padrão

Implementada em `src/context_anchor/policy.py`.

A ausência de cadastro prévio não é motivo suficiente para negar uma ação que o perfil local e o sistema operacional conseguem executar.

Atualmente:

- `open_app` não depende de `SUPPORTED_APP_IDS` para autorização;
- URLs HTTP/HTTPS públicas, privadas ou locais são aceitas pela política local;
- nomes de tecla imprimíveis não dependem de lista fechada;
- ações ainda sem executor implementado falham por ausência de implementação, não por allowlist.

Bloqueios específicos futuros devem entrar como denylist ou regras explícitas.

## 9. Resolução de aplicativos e processos

Backend em `src/context_anchor/desktop.py`.

`APP_COMMANDS` e `APP_ALIASES` são resolvedores convenientes, não fronteira de autorização.

Para `open_app`, o backend tenta:

1. aliases/candidatos conhecidos;
2. executável/comando informado;
3. variações simples de nome quando aplicável.

Argumentos são separados por `shlex.split(...)` e o processo atual usa `subprocess.Popen(..., shell=False)`.

Brave possui candidatos `brave-browser`, `brave-browser-stable` e `brave`.

## 10. Browser

`open_url` é executado por Playwright/Chromium em `src/context_anchor/actions.py`.

Abrir um navegador instalado é `open_app`; navegar para endereço é `open_url`.

Um pedido genérico `abrir navegador e acessar <domínio>` usa `open_url`. Um navegador explicitamente nomeado é aberto como aplicativo com a URL como argumento.

### Contexto entre tarefas

O executor Playwright permanece vivo enquanto o processo do Robô estiver vivo, mas um navegador externo aberto por `open_app`, como Brave, não possui ainda uma sessão lógica persistida no planner.

Consequentemente, um pedido posterior isolado como `agora pesquise ...` não deve ser interpretado como garantia de continuar naquele Brave específico. Se continuidade entre tarefas for necessária, será preciso persistir explicitamente o contexto de navegador/alvo ativo.

## 11. Desktop, Unicode, foco e FAILSAFE

O desktop físico usa PyAutoGUI no Linux/X11.

### Digitação

`type_text()` separa a digitação em dois caminhos:

- trechos ASCII → `pyautogui.write(...)`;
- caracteres não ASCII → entrada Unicode do Linux com `Ctrl+Shift+U`, código hexadecimal do caractere e Enter.

Isso evita depender de `pyautogui.write()` para caracteres como `á` e `ç`.

O resultado registra o método de entrada usado, não o conteúdo digitado.

### Foco

Ao abrir um aplicativo ou clicar, a janela observada pode se tornar o foco esperado. Antes de `type_text` e `press_key`, mudança de janela observável é recusada.

### FAILSAFE

Além do `pyautogui.FAILSAFE`, o backend verifica uma zona própria de 20 pixels nos quatro cantos antes de entrada física.

## 12. Emergency stop

`src/context_anchor/emergency_stop.py` usa sentinel persistente, PID + identidade Linux e bloqueio de reinício até liberação consciente.

Permanece independente do planner e dos providers.

## 13. Providers

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

## 14. Credenciais e telemetria

Credenciais permanecem fora de código, Git, prompts e logs.

Telemetria real por componente:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Resultados de objetivo podem incluir etapas, provider, rota e fallbacks sem incluir tokens.

## 15. Percepção atual

Já existem screenshot e janela ativa.

Ainda não existem árvore de acessibilidade, percepção semântica de screenshots nem visão multimodal integrada ao loop.

## 16. Acesso remoto

Painel e Central continuam localhost. Publicação remota ainda não foi implementada.

Canais futuros continuam Web remoto, WhatsApp, Telegram e Instagram.

## 17. Estado de validação

Estão **PASS** fisicamente:

- `Abra o editor de texto e escreva Olá mundo`;
- `Abra o navegador e acesse o site globo.com`;
- `Abra o navegador brave e acesse o site google.com`.

Antes da correção de pesquisa, ficaram **FAIL**:

- `Abra o navegador brave e acesse o site google.com e pesquise o significado do nome Josiel`;
- `agora pesquise sobre inteligencia artificial`.

A correção desses dois padrões passou no GitHub Actions CI run `31307745802` e aguarda revalidação física.
