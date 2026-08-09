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
  ├─ Determinístico ativo
  └─ Contrato provider-agnostic para IA
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

Painel ─┐
Central ├─→ runtime/logs/{panel,central,robot}.log ─→ Painel
Robô ───┘
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
- oferecer controles de Central, Robô e emergência cujo texto, cor e ação refletem o estado real atual;
- distinguir quando a Central está ligada mas foi iniciada fora do Painel;
- iniciar/parar Central;
- iniciar/parar/reiniciar Robô;
- alterar a configuração local de Desktop;
- executar diagnóstico de leitura;
- mostrar tarefas recentes com representação diferente de `queued`, `running`, `succeeded` e `failed`;
- mostrar telemetria real de Painel, Central e Robô;
- enviar tarefas à Central usando o token local já configurado no servidor;
- explicar comandos de desenvolvimento no Laboratório.

O Painel não possui endpoint de shell arbitrário.

O campo de tarefa envia texto ao planner do Robô. O Laboratório de comandos é uma interface separada: comandos conhecidos recebem explicações; comandos desconhecidos não são executados automaticamente.

### 1.1 Controles orientados por estado

Os controles de operação não são botões estáticos de comando.

A cada atualização de `/api/status`, o Painel recalcula:

- estado atual da Central;
- se a Central é gerenciada pelo Painel ou foi iniciada externamente;
- estado atual do Robô;
- estado da parada de emergência;
- próxima ação válida para cada componente.

Exemplos:

- Central desligada → ação exibida: **Ligar Central**;
- Central ligada e gerenciada → ação exibida: **Parar Central**;
- Central ligada externamente → estado **Ligada fora do Painel**, sem fingir que o Painel consegue encerrá-la;
- Robô desligado com emergência ativa → início bloqueado visualmente;
- emergência normal → ação **Ativar emergência**;
- emergência ativa → ação **Liberar emergência**.

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

## 2.1 Telemetria e logs de runtime

Implementada em `src/context_anchor/runtime_log.py` e usada diretamente por Painel, Central e Robô.

Arquivos estruturados:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Cada linha contém timestamp com timezone, nível e evento operacional. Esses eventos são gravados pelo próprio componente, portanto não dependem de o processo ter sido iniciado pelo Painel.

O Painel lê os arquivos, combina os eventos e permite filtrar por **Todos / Painel / Central / Robô**.

Quando o Painel inicia Central ou Robô, `stdout/stderr` bruto desses subprocessos é separado em `central-process.log` e `robot-process.log`; isso evita confundir saída bruta do processo com os eventos estruturados apresentados na interface.

A telemetria estruturada registra ids de tarefas, estados, falhas e transições operacionais. Credenciais não são registradas, e o logger de runtime não grava o texto bruto dos comandos enviados pelo usuário.

## 3. Central

Implementada em `src/context_anchor/control_plane.py`.

Responsabilidades:

- autenticação separada de usuário e Robô;
- criação e consulta de tarefas;
- persistência;
- entrega de tarefa ao Robô;
- emissão de lease;
- recepção de resultado protegido pelo lease;
- emissão de eventos estruturados de criação, entrega, conclusão e rejeição de resultado.

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
9. envia resultado;
10. registra eventos operacionais reais sem expor credenciais.

Comando humano: `robo`.

## 6. Planner

Contrato em `src/context_anchor/planner.py`.

Estado atual:

- `DeterministicPlanner` ativo;
- `StructuredAction` fechado para ações conhecidas;
- `ProviderPlanner` preparado para integração externa;
- nenhum provedor externo está executando tarefas ainda.

A primeira integração escolhida é **Cerebras** com o modelo **`gpt-oss-120b`**.

A arquitetura não deve acoplar o Robô diretamente à Cerebras. O caminho previsto é:

```text
pedido do usuário
      ↓
ProviderPlanner
      ↓
adaptador Cerebras
      ↓
resposta estruturada
      ↓
StructuredAction
      ↓
Policy Layer
      ↓
executor permitido
```

O adaptador de provedor deverá ser substituível. Uma eventual troca para outro serviço não deve alterar a Policy Layer, os executores físicos, o FAILSAFE ou a parada de emergência.

A chave de API da Cerebras deverá existir apenas em configuração local/variável de ambiente e não poderá ser enviada ao Git, aos logs ou ao prompt do modelo.

Não há campo de shell, código livre, caminho de executável arbitrário ou credenciais no contrato.

Google/Gemini pode futuramente ser conectado como fallback, mas não existe roteamento multi-provider implementado no MVP 0.3.

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

### 9.1 FAILSAFE explícito de entrada física

O backend mantém `pyautogui.FAILSAFE = True`, mas não depende dele como única proteção porque esse mecanismo falhou no primeiro teste físico real.

Antes das ações `move_mouse`, `click_mouse`, `type_text` e `press_key`, o backend executa uma verificação própria da posição atual do ponteiro.

Uma margem de 20 pixels nos quatro cantos da tela forma a zona de segurança:

```text
ponteiro em canto seguro
        ↓
DesktopFailsafeTriggered
        ↓
nenhum movimento/clique/tecla é enviado
        ↓
Robô reporta tarefa como failed
        ↓
telemetria registra a falha
```

O FAILSAFE explícito é uma interrupção imediata da próxima entrada física. Ele não substitui a parada de emergência persistente, que encerra o processo do Robô e impede reinício até liberação consciente.

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

A chave do primeiro provedor de IA seguirá a mesma regra: somente configuração local/variável de ambiente consumida pelo adaptador do planner.

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
