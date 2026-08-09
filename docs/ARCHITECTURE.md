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
  ├─ estado real / configuração / diagnóstico / aprendizado
  ├─ controles de processo orientados pelo estado atual
  ├─ tarefas recentes
  ├─ telemetria real de Painel / Central / Robô
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
  ├─ DeterministicPlanner ativo
  └─ ProviderPlanner provider-agnostic
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

Implementado em `src/context_anchor/dashboard.py`.

Comando humano: `painel-robo`.

Bind padrão: `127.0.0.1:8765`.

Responsabilidades atuais:

- mostrar estado de Central, Robô, Desktop e emergência;
- iniciar/parar Central;
- iniciar/parar/reiniciar Robô;
- alterar configurações locais explicitamente suportadas;
- executar diagnóstico de leitura;
- mostrar tarefas recentes e telemetria real;
- enviar tarefas à Central;
- explicar comandos de desenvolvimento no Laboratório.

O Painel não possui endpoint de shell arbitrário.

## 2. Central

Implementada em `src/context_anchor/control_plane.py`.

Responsabilidades:

- autenticação separada de usuário e Robô;
- criação e consulta de tarefas;
- persistência;
- entrega de tarefa ao Robô;
- emissão de lease;
- recepção de resultado protegido pelo lease;
- registro de eventos operacionais.

Bind padrão: `127.0.0.1:8000`.

## 3. Persistência e leases

Implementada em `src/context_anchor/store.py` com SQLite.

Fluxo:

```text
queued
  ↓ claim + lease
running
  ↓
succeeded | failed
```

Tarefa abandonada pode retornar à fila após expiração do lease. Resultados atrasados com lease antigo são rejeitados.

## 4. Robô local

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
9. envia resultado;
10. registra telemetria.

## 5. Planner

Contrato em `src/context_anchor/planner.py`.

Estado atual:

- `DeterministicPlanner` é o planner ativo;
- `StructuredAction` aceita apenas ações conhecidas;
- `ProviderPlanner` existe para integração externa;
- nenhum provedor externo está ativo ainda.

A arquitetura deve permanecer **provider-agnostic**. O caminho previsto para qualquer provedor é:

```text
pedido do usuário
      ↓
ProviderPlanner
      ↓
adaptador do provedor selecionado
      ↓
resposta estruturada
      ↓
StructuredAction
      ↓
Policy Layer
      ↓
executor permitido
```

A seleção atual do primeiro provedor está em avaliação entre SiliconFlow, Z.AI/GLM, Cloudflare Workers AI e Groq. Essa avaliação não altera o contrato interno do planner.

Trocar de provedor não deve exigir alterações na Policy Layer, nos executores físicos, no FAILSAFE ou na parada de emergência.

O adaptador do provedor deverá tratar erros, rate limits e respostas inválidas sem derrubar o Robô.

## 6. Credenciais de provedores

Chaves de API não entram em código, Git, logs ou prompts.

Quando um provedor for escolhido, sua chave será consumida somente por variável de ambiente/configuração local do adaptador.

Contas e chaves já foram criadas externamente para SiliconFlow e Z.AI, mas nenhuma foi integrada ao código até o momento.

## 7. Policy Layer

Implementada em `src/context_anchor/policy.py`.

Toda ação produzida por planner determinístico ou por IA futura passa pela mesma camada de política.

### Navegador

- apenas HTTP/HTTPS;
- localhost, `.local`, IPs privados, loopback, link-local e reservados permanecem bloqueados.

### Desktop

- feature gate `CONTEXT_ANCHOR_DESKTOP_ENABLED`;
- ações tipadas;
- coordenadas validadas;
- texto limitado;
- teclas permitidas por lista;
- aplicativos por allowlist fixa.

## 8. Navegador

Implementado em `src/context_anchor/actions.py` com Playwright/Chromium.

Preferência arquitetural:

```text
API/DOM
→ automação estruturada
→ acessibilidade
→ visão + mouse/teclado como fallback
```

## 9. Desktop

Backend em `src/context_anchor/desktop.py`.

Capacidades atuais:

- screenshot;
- janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo/direito;
- digitar texto;
- teclas permitidas;
- abrir aplicativos permitidos.

Backend físico inicial: Linux/X11.

### FAILSAFE explícito

Além de `pyautogui.FAILSAFE = True`, o backend verifica a posição atual do ponteiro antes de qualquer entrada física.

Uma margem de 20 pixels nos quatro cantos funciona como zona de interrupção. Se o ponteiro estiver nessa zona, a ação gera `DesktopFailsafeTriggered` antes de mover, clicar ou digitar.

## 10. Aplicativos

Ids conhecidos são mapeados para executáveis permitidos e abertos com `shell=False`.

O Robô não aceita linha de shell arbitrária recebida da tarefa.

## 11. Percepção

Primeiro slice implementado:

- screenshot;
- janela ativa.

Ainda faltam árvore de acessibilidade, percepção semântica da imagem e fusão de fontes de percepção.

## 12. Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py`.

- sentinel persistente;
- PID + identidade Linux;
- encerramento independente do planner;
- bloqueio de reinício até liberação consciente.

## 13. Diagnóstico e telemetria

Diagnóstico em `src/context_anchor/doctor.py`.

Telemetria estruturada em `src/context_anchor/runtime_log.py`:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Credenciais não são registradas.

## 14. Gerenciamento de processos

Implementado em `src/context_anchor/process_registry.py`.

Registros guardam PID e tempo de início para evitar agir sobre PID reutilizado. Processos Linux em estado `Z` são tratados como desligados.

## 15. Acesso remoto — futuro

Antes de publicar Painel ou Central na Internet serão necessários TLS, autenticação forte, pareamento, revogação, rate limiting, proteção contra replay, auditoria e confirmação para ações sensíveis.

## 16. Canais — futuro

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

## 17. Princípio local-first

O controle físico permanece no Robô local. Painel, serviços externos e canais futuros enviam intenção e recebem resultado; nenhuma camada externa acessa diretamente mouse, teclado, câmera ou aplicativos sem passar pelo Robô e pela Policy Layer.