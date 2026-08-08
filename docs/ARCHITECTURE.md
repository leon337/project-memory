# ARCHITECTURE

## Estado arquitetural atual

```text
Usuário
  ↓
Painel Web local
  ↓
Control Plane — FastAPI
  ↓
SQLite — fila, histórico e leases
  ↓
HTTP polling autenticado
  ↓
Agente local
  ↓
Planner
  ├─ Determinístico ativo
  └─ Contrato estruturado para provedor futuro
  ↓
Policy Layer
  ├─ Browser policy
  └─ Desktop policy + feature gate local
  ↓
Executores
  ├─ Playwright / Chromium
  └─ PyAutoGUI / Linux desktop
  ↓
Verificação do resultado
  ↓
Control Plane
```

O controle físico permanece local. O Control Plane envia intenções/tarefas; o agente local decide, pela Policy Layer, se a ação tipada pode ser executada.

## 1. Control Plane

Implementado em `src/context_anchor/control_plane.py`.

Responsabilidades:

- painel Web;
- autenticação do usuário;
- autenticação separada do agente;
- criação e consulta de tarefas;
- entrega de tarefas ao agente;
- emissão de lease por execução;
- recepção de resultado protegido pelo token do lease.

Por padrão escuta apenas `127.0.0.1`.

## 2. Persistência e leases

Implementada em `src/context_anchor/store.py` com SQLite.

Fluxo:

```text
queued
  ↓ claim + lease
running
  ↓
succeeded | failed
```

Se um lease expirar antes da conclusão, a tarefa pode voltar a `queued`. Depois do limite de tentativas, ela passa a `failed`.

Cada claim gera um `lease_token` novo. Um resultado só é aceito se o token ainda pertencer à execução atual, impedindo que um agente atrasado finalize uma tarefa já retomada.

Dados relevantes:

- id e comando;
- status;
- timestamps;
- agente atual;
- resultado/erro;
- lease e expiração;
- número de tentativas.

## 3. Agente local

Implementado em `src/context_anchor/local_agent.py`.

Fluxo atual:

1. verifica emergency stop;
2. registra sua identidade de processo local;
3. autentica no Control Plane;
4. reivindica uma tarefa e seu lease;
5. pede um plano ao planner ativo;
6. passa o plano pela Policy Layer;
7. executa a ação autorizada;
8. verifica o resultado;
9. devolve resultado junto ao lease da execução.

## 4. Planner

O contrato está em `src/context_anchor/planner.py`.

Existem hoje:

- `DeterministicPlanner`, ativo;
- `StructuredAction`, esquema fechado para ações conhecidas;
- `ProviderPlanner`, adaptador para um provedor futuro;
- `StructuredPlanProvider`, protocolo de integração.

O contrato não possui campo para shell, código, caminho de executável livre ou credenciais.

Mesmo uma saída estruturalmente válida ainda precisa ser autorizada pela Policy Layer.

## 5. Policy Layer

Implementada em `src/context_anchor/policy.py`.

### Navegador

- apenas HTTP/HTTPS;
- bloqueio de localhost, `.local`, IPs privados, loopback, link-local e reservados.

### Desktop

- desktop desativado por padrão;
- ações precisam pertencer à allowlist tipada;
- coordenadas possuem validação;
- texto limitado a 500 caracteres e sem quebra de linha dentro da mesma ação;
- teclas aceitas pertencem a allowlist específica;
- aplicativos pertencem a allowlist fixa.

## 6. Browser Layer

Implementada em `src/context_anchor/actions.py` com Playwright/Chromium.

Verificação atual:

- URL solicitada;
- URL final;
- título;
- status HTTP;
- `verified`.

Preferência arquitetural permanece:

```text
API/DOM
→ automação estruturada
→ acessibilidade
→ visão + mouse/teclado como fallback
```

## 7. Desktop Action Layer

Backend físico em `src/context_anchor/desktop.py`.

Capacidades atuais:

- screenshot;
- janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo/direito;
- digitar texto;
- pressionar teclas permitidas;
- abrir aplicativos permitidos.

PyAutoGUI é importado de forma lazy para que processos de servidor e CI não exijam sessão gráfica apenas para importar o pacote.

O backend inicial considera Linux/X11. Wayland permanece não validado.

## 8. Application Registry

O agente não aceita nome de executável arbitrário.

O registro interno mapeia ids estáveis para executáveis conhecidos, como Firefox, Chromium, Nemo/Nautilus, Xed/Gedit, VS Code, calculadora e LibreOffice.

A abertura usa `subprocess.Popen` com `shell=False`.

## 9. Perception Layer

Primeiro slice implementado:

- screenshot;
- metadado de janela ativa quando `xdotool` está disponível.

Ainda faltam:

- árvore de acessibilidade;
- percepção semântica da tela;
- DOM compartilhado como contexto para planner;
- fusão de múltiplas fontes de percepção.

## 10. Emergency Stop

Implementado em `src/context_anchor/emergency_stop.py`.

Mecanismos:

- sentinel persistente em arquivo;
- PID do agente acompanhado do tempo de início do processo Linux;
- verificação contra reutilização de PID;
- `SIGTERM` direto ao processo local quando a identidade confere;
- agente recusa reinício enquanto o sentinel existir;
- configuração do stop não depende das credenciais do agente.

Isso é separado do planner e não depende de uma decisão do modelo.

## 11. Diagnóstico local

`src/context_anchor/doctor.py` fornece `context-anchor-doctor`.

Ele apenas observa o ambiente e informa dependências/sessão gráfica; não executa ações físicas.

## 12. Credenciais

Credenciais não devem aparecer:

- no código;
- nos prompts;
- nos logs;
- no Git;
- diretamente no modelo.

`.env` permanece fora do repositório. Usuário e agente possuem tokens separados.

## 13. Control Plane remoto — planejado

Antes de exposição à Internet ainda são necessários:

- TLS;
- autenticação forte;
- pareamento de dispositivo;
- revogação/rotação;
- rate limiting;
- proteção contra replay;
- auditoria adequada;
- confirmação humana para ações sensíveis.

## 14. Channel Adapters — planejados

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

Nenhum adaptador de mensageria foi implementado ainda.

## 15. Princípio local-first

Serviços externos poderão enviar objetivos e receber resultados, mas não terão acesso direto ao mouse, teclado, câmera ou aplicativos. Toda ação física deverá passar pelo agente local, pelo feature gate e pela Policy Layer.
