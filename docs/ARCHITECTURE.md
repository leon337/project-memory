# ARCHITECTURE

## Terminologia usada

Para facilitar operação e aprendizado:

- **Painel do Robô** = gerenciador local de operação, configuração, diagnóstico e aprendizado;
- **Central** = processo técnico `Control Plane`;
- **Robô local** = processo técnico `local agent`;
- **Central Web antiga** = interface simples ainda servida pela Central em `127.0.0.1:8000`, mantida por compatibilidade durante a transição.

## Arquitetura implementada no MVP 0.3

```text
Usuário
  ↓
Painel do Robô — FastAPI :8765
  ├─ status / configuração / diagnóstico / aprendizado
  ├─ gerenciamento local de processos
  ├─ tarefas recentes e logs
  └─ envio de tarefa
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
  ├─ Determinístico ativo
  └─ Contrato estruturado para IA futura
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

Painel, Central e Robô são processos separados.

A separação permite que o Painel continue disponível para diagnosticar ou religar os outros dois processos.

## 1. Painel do Robô

Implementado em `src/context_anchor/dashboard.py`.

Comando humano:

```text
painel-robo
```

Bind padrão:

```text
127.0.0.1:8765
```

Responsabilidades atuais:

- mostrar estado de Central, Robô, Desktop e emergência;
- iniciar/parar Central;
- iniciar/parar/reiniciar Robô;
- alterar a configuração local de Desktop;
- executar diagnóstico de leitura;
- mostrar tarefas recentes;
- mostrar logs de processos iniciados pelo Painel;
- enviar tarefas à Central usando o token local já configurado no servidor;
- explicar comandos de desenvolvimento no Laboratório.

O Painel não possui endpoint de shell arbitrário.

O campo de tarefa envia texto ao planner do Robô. O Laboratório de comandos é uma interface separada: comandos conhecidos recebem explicações; comandos desconhecidos não são executados automaticamente.

## 2. Registro e controle de processos

Implementado em `src/context_anchor/process_registry.py`.

Um registro de processo contém:

- PID;
- tempo de início obtido de `/proc/<pid>/stat`.

Antes de enviar um sinal de encerramento, PID e tempo de início precisam coincidir. Isso reduz o risco de agir sobre outro processo caso o Linux reutilize um PID antigo.

Registros atuais:

- Central: `runtime/central.pid`;
- Robô: `runtime/local_agent.pid`.

A Central nova registra sua identidade quando inicia. O Robô já possuía registro por causa da parada de emergência.

## 3. Central

Implementada em `src/context_anchor/control_plane.py`.

Responsabilidades:

- autenticação separada de usuário e Robô;
- criação e consulta de tarefas;
- persistência;
- entrega de tarefa ao Robô;
- emissão de lease;
- recepção de resultado protegido pelo lease.

Bind padrão: `127.0.0.1:8000`.

Comando humano: `central`.

## 4. Persistência e leases

Implementada em `src/context_anchor/store.py` com SQLite.

Fluxo:

```text
queued
  ↓ claim + lease
running
  ↓
succeeded | failed
```

Tarefa abandonada pode retornar à fila após expiração do lease. Há limite de tentativas e resultado atrasado com lease antigo é rejeitado.

`list_recent()` fornece ao Painel uma visão recente da fila/histórico sem alterar propriedade das tarefas.

## 5. Robô local

Implementado em `src/context_anchor/local_agent.py`.

Fluxo:

1. verifica parada de emergência;
2. registra identidade do processo;
3. autentica na Central;
4. busca tarefa;
5. obtém plano;
6. valida na Policy Layer;
7. executa;
8. verifica;
9. envia resultado.

Comando humano: `robo`.

## 6. Planner

Contrato em `src/context_anchor/planner.py`.

Atual:

- `DeterministicPlanner` ativo;
- `StructuredAction` fechado para ações conhecidas;
- `ProviderPlanner` preparado para provedor futuro.

Não há campo de shell, código livre, caminho de executável arbitrário ou credenciais no contrato.

## 7. Policy Layer

Implementada em `src/context_anchor/policy.py`.

### Navegador

- HTTP/HTTPS;
- localhost, `.local`, IPs privados/loopback/link-local/reservados bloqueados.

### Desktop

- feature gate `CONTEXT_ANCHOR_DESKTOP_ENABLED`;
- ações tipadas;
- coordenadas validadas;
- texto limitado;
- teclas permitidas por lista;
- aplicativos por allowlist fixa.

## 8. Navegador

Implementado em `src/context_anchor/actions.py` com Playwright/Chromium.

Verifica URL solicitada, URL final, título, status HTTP e `verified`.

Preferência arquitetural:

```text
API/DOM
→ automação estruturada
→ acessibilidade
→ visão + mouse/teclado como fallback
```

## 9. Desktop

Backend em `src/context_anchor/desktop.py`.

Capacidades em código:

- screenshot;
- janela ativa por `xdotool`;
- mover mouse;
- clique esquerdo/direito;
- digitar texto;
- teclas permitidas;
- abrir aplicativos permitidos.

Backend físico inicial: Linux/X11. Wayland não validado.

## 10. Aplicativos

Ids conhecidos são mapeados para executáveis permitidos.

A abertura usa `subprocess.Popen(..., shell=False)`.

O Robô não aceita caminho de executável ou linha de shell arbitrária recebida da tarefa.

## 11. Percepção

Primeiro slice em código:

- screenshot;
- janela ativa.

Ainda faltam árvore de acessibilidade, percepção semântica da imagem e fusão de fontes de percepção.

## 12. Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py`.

- sentinel persistente;
- PID + identidade Linux;
- `SIGTERM` quando a identidade confere;
- bloqueia reinício até limpeza consciente;
- independente do planner e das credenciais do Robô.

Comando humano: `parar-robo`.

O Painel também possui controles para ativar e limpar o estado de emergência.

## 13. Diagnóstico

`src/context_anchor/doctor.py` observa o ambiente sem executar ações físicas.

Comando humano: `diagnostico-robo`.

O mesmo coletor de diagnóstico é reutilizado pelo Painel.

## 14. Configuração local

`.env` permanece fora do Git.

O Painel pode alterar apenas configurações explicitamente suportadas. No MVP 0.3, a alteração visual implementada é `CONTEXT_ANCHOR_DESKTOP_ENABLED`.

Outras configurações deverão ser expostas individualmente, nunca por edição arbitrária de arquivo via interface.

## 15. Credenciais

Credenciais não devem ser colocadas em código, prompts, logs ou Git.

Painel e Central continuam locais. O Painel usa internamente a credencial local configurada para enviar tarefas à Central, evitando exigir que o usuário cole o token em cada tarefa.

## 16. Acesso remoto — futuro

Antes de publicar Painel ou Central na Internet serão necessários TLS, autenticação forte, pareamento, revogação, rate limiting, proteção contra replay, auditoria e confirmação para ações sensíveis.

## 17. Canais — futuro

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

Nenhum adaptador de mensageria foi implementado ainda.

## 18. Princípio local-first

O controle físico continua no Robô local. Painel, serviços externos ou canais futuros enviam intenção e recebem resultado; nenhuma camada externa acessa diretamente mouse, teclado, câmera ou aplicativos sem passar pelo Robô e pela Policy Layer.
