# ARCHITECTURE

## Estado arquitetural atual

O primeiro MVP está implementado como dois processos separados:

```text
Usuário
  ↓
Painel Web local
  ↓
Control Plane — FastAPI
  ↓
SQLite — fila e histórico de tarefas
  ↓
HTTP polling autenticado
  ↓
Agente local
  ↓
Planner determinístico
  ↓
Policy Layer
  ↓
Playwright / Chromium
  ↓
Verificação do resultado
  ↓
Control Plane
  ↓
Painel Web
```

A separação entre Control Plane e agente local já existe mesmo quando ambos rodam inicialmente na mesma máquina.

## 1. Control Plane

Implementado em `src/context_anchor/control_plane.py`.

Responsabilidades atuais:

- servir o painel Web;
- autenticar o usuário;
- autenticar separadamente o agente local;
- receber comandos;
- criar tarefas;
- fornecer a próxima tarefa ao agente;
- receber o resultado;
- permitir consulta do estado da tarefa.

Por padrão escuta apenas `127.0.0.1`.

## 2. Persistência

Implementada em `src/context_anchor/store.py` com SQLite.

Estados atuais:

```text
queued
  ↓
running
  ↓
succeeded | failed
```

Cada tarefa registra:

- id;
- comando;
- estado;
- criação e atualização;
- agente que reivindicou a tarefa;
- resultado estruturado;
- erro quando houver.

SQLite foi escolhido para o MVP por simplicidade e porque o Control Plane atual possui um único escritor lógico.

## 3. Agente local

Implementado em `src/context_anchor/local_agent.py`.

O agente:

1. autentica no Control Plane com token próprio;
2. consulta periodicamente a próxima tarefa;
3. transforma o comando em um plano;
4. consulta a política;
5. executa apenas se autorizado;
6. verifica o resultado;
7. devolve sucesso ou falha ao Control Plane.

O agente local continua sendo o único componente autorizado a controlar recursos físicos do computador.

## 4. Planner atual

Implementado em `src/context_anchor/policy.py`.

O primeiro planner é determinístico e não usa modelo de IA.

Comandos suportados:

- `abrir <site>`;
- `open <site>`;
- `pesquisar <termo>`;
- `buscar <termo>`;
- `search <termo>`.

Essa escolha valida o ciclo operacional antes de adicionar a variabilidade de um LLM.

O planner futuro deverá produzir ações estruturadas no mesmo contrato, permitindo trocar o mecanismo de raciocínio sem alterar o executor.

## 5. Policy Layer

Também implementada em `src/context_anchor/policy.py`.

A política atual:

- permite apenas a ação `open_url`;
- permite apenas HTTP e HTTPS;
- bloqueia `localhost`;
- bloqueia domínios `.local`;
- bloqueia IPs privados, loopback, link-local e reservados;
- rejeita comandos não reconhecidos.

A evolução deverá adicionar categorias de risco, confirmação humana e políticas específicas por capacidade sem remover a decisão central de autorização antes da execução.

## 6. Browser Layer

Implementada em `src/context_anchor/actions.py` com Playwright e Chromium.

O navegador é mantido aberto pelo processo do agente enquanto ele estiver em execução.

A verificação atual retorna:

- URL solicitada;
- URL final;
- título da página;
- status HTTP quando disponível;
- indicador `verified`.

A preferência arquitetural continua sendo:

```text
API/DOM
→ automação estruturada
→ acessibilidade
→ visão + mouse/teclado como fallback
```

## 7. Credenciais

Credenciais não podem ser armazenadas:

- no código;
- nos prompts;
- nos logs;
- no Git;
- diretamente no modelo de IA.

O repositório contém apenas `.env.example`. O arquivo `.env` real está ignorado pelo Git.

O MVP usa dois segredos separados:

- `CONTEXT_ANCHOR_USER_TOKEN`;
- `CONTEXT_ANCHOR_AGENT_TOKEN`.

Nenhum mecanismo de login de terceiros é contornado. Sessões autenticadas de navegador deverão ser reutilizadas por mecanismos próprios quando essa capacidade for implementada.

## 8. Perception Layer — planejada

Ainda não implementada.

A evolução deverá combinar, nessa ordem de preferência:

- DOM quando disponível;
- árvore de acessibilidade;
- metadados de janelas;
- screenshot;
- visão computacional como fallback.

O sistema não deverá depender exclusivamente de coordenadas da tela.

## 9. Desktop Action Layer — planejada

Ainda não implementada.

Capacidades futuras:

- mouse;
- teclado;
- gerenciamento de janelas;
- abertura de aplicativos permitidos;
- arquivos autorizados;
- câmera quando explicitamente habilitada.

Essas ações deverão passar pela mesma Policy Layer antes da execução.

## 10. Emergency Stop — planejado

Ainda não implementado.

Deverá existir um mecanismo independente do modelo e do loop do agente para interromper imediatamente a execução local.

## 11. Control Plane remoto — planejado

O painel atual é local.

Antes de exposição à Internet serão necessários pelo menos:

- TLS;
- autenticação mais forte;
- pareamento de dispositivo;
- rotação/revogação de credenciais;
- rate limiting;
- proteção contra replay;
- trilha de auditoria adequada;
- política de confirmação para ações sensíveis.

## 12. Channel Adapters — planejados

WhatsApp, Telegram e Instagram permanecem desacoplados do núcleo.

Arquitetura-alvo:

```text
Web Adapter
WhatsApp Adapter
Telegram Adapter
Instagram Adapter
        ↓
Command Gateway
        ↓
Control Plane
        ↓
Agente local
```

Nenhum desses adaptadores de mensageria foi implementado ainda.

## 13. Princípio local-first

O controle físico permanece no agente local.

Serviços externos poderão enviar intenções e receber resultados, mas não terão acesso direto ao mouse, teclado, câmera ou aplicativos sem passar pelo agente local e pela política de autorização.
