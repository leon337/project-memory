# STATUS

## Objetivo atual

Construir um agente autônomo capaz de operar o computador do usuário como um operador digital, sempre dentro das permissões concedidas pelo usuário e pelo sistema operacional.

O objetivo final continua incluindo mouse, teclado, aplicativos, navegador, sites, sessões autenticadas, percepção da tela, câmera autorizada, tarefas compostas e controle remoto por Web, WhatsApp, Telegram e Instagram.

## Estado verificável agora

O branch `main` contém o **MVP 0.3** em código.

O projeto possui três processos separados:

- **Painel do Robô** — interface local de operação e aprendizado;
- **Central** — recebe, persiste e distribui tarefas;
- **Robô local** — executa ações permitidas no computador.

## Painel do Robô — implementado e em validação física

Implementado em `src/context_anchor/dashboard.py` e iniciado por:

```text
painel-robo
```

Por padrão escuta somente `127.0.0.1:8765`.

Capacidades atuais:

- estado visual da Central, Robô, Desktop e emergência;
- ligar/parar Central;
- ligar/parar/reiniciar Robô;
- alterar `CONTEXT_ANCHOR_DESKTOP_ENABLED` pelo painel;
- diagnóstico local;
- tarefas recentes;
- envio de tarefas sem digitar token no navegador;
- logs de Central e Robô quando gerenciados pelo Painel;
- laboratório de comandos guiados;
- áreas Visão geral, Configurações e Laboratório.

O laboratório não executa shell arbitrário. Comandos desconhecidos são apenas explicados como não catalogados.

## Gerenciamento de processos

Implementado em `src/context_anchor/process_registry.py`.

- registros de processo guardam PID e tempo de início no Linux;
- a identidade é verificada antes de encerrar um processo;
- a Central registra `runtime/central.pid`;
- o Robô registra `runtime/local_agent.pid`;
- o Painel administra processos compatíveis com esses registros.

## Comandos humanos atuais

- `painel-robo` — Painel do Robô;
- `central` — Central;
- `robo` — Robô local;
- `parar-robo` — parada de emergência;
- `diagnostico-robo` — diagnóstico.

Aliases técnicos antigos permanecem por compatibilidade.

## Central e tarefas

- FastAPI;
- autenticação separada para usuário e Robô;
- SQLite como fila e histórico;
- polling HTTP autenticado;
- estados `queued`, `running`, `succeeded` e `failed`;
- leases com token de propriedade;
- recuperação de tarefas interrompidas e limite de tentativas;
- `TaskStore.list_recent()` para tarefas recentes no Painel.

## Navegador

- Playwright + Chromium;
- comandos `abrir <site>` e `pesquisar/buscar <termo>`;
- verificação de URL final, título e status HTTP;
- bloqueio de localhost, `.local`, IPs privados/loopback e esquemas não HTTP(S).

## Desktop

Implementado em `src/context_anchor/desktop.py` com PyAutoGUI carregado somente quando necessário.

Ações tipadas atuais:

- screenshot;
- janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo e direito;
- digitar texto limitado;
- teclas permitidas;
- abrir aplicativos de allowlist fixa.

Aplicativos são iniciados com `shell=False`; nomes remotos não viram comandos arbitrários.

## Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py`.

- marcador persistente `runtime/EMERGENCY_STOP`;
- Robô se recusa a iniciar enquanto o marcador existir;
- PID + identidade de processo verificados antes de `SIGTERM`;
- independente do planner/modelo;
- PyAutoGUI mantém `FAILSAFE` habilitado.

## Diagnóstico

`diagnostico-robo` e o Painel verificam Python, sistema, sessão gráfica, `DISPLAY`/Wayland, PyAutoGUI, `xdotool`, `scrot` e aplicativos permitidos.

## Planner

- planner determinístico continua ativo;
- contrato provider-agnostic em `src/context_anchor/planner.py`;
- saída estruturada aceita somente ações conhecidas;
- não existe ação `shell` no esquema;
- toda ação continua passando pela Policy Layer;
- nenhum provedor de IA real foi ativado ainda.

## Validação automatizada

- GitHub Actions instala dependências, compila e executa `pytest`;
- CI do commit `3bffd1bf8bca5093d399ce2f98b26a27eceadc48`, contendo o Painel, endpoints tipados e testes do laboratório, concluiu com sucesso;
- testes verificam a ausência de endpoint genérico `/api/shell`;
- testes anteriores de Central, desktop, emergency stop, planner, política e leases continuam no pipeline.

## Validação física — Linux real

Já confirmado no computador alvo:

- sessão `X11` e `DISPLAY=:0.0`;
- `xdotool` e `scrot` instalados;
- Firefox, Chrome/Chromium, Xed, VS Code, calculadora e LibreOffice detectados;
- Central em `127.0.0.1:8000` funcionando;
- Robô fazendo polling autenticado;
- `abrir example.com` executado fisicamente com sucesso;
- `pesquisar inteligência artificial` executado fisicamente com sucesso;
- comandos `central`, `robo` e `painel-robo` instalados dentro da `.venv`;
- `.env` local está com `CONTEXT_ANCHOR_DESKTOP_ENABLED=true`;
- `painel-robo` iniciou fisicamente em `127.0.0.1:8765`;
- Visão geral, Configurações e Laboratório abriram corretamente no navegador;
- o Painel detectou Central ligada, Robô ligado, Desktop habilitado e emergência normal;
- foi criado localmente um atalho `.desktop` em `/home/leo/Área de trabalho/Painel do Robo.desktop` e ele inicia o Painel;
- o botão **Reiniciar Robô** foi acionado fisicamente pelo Painel;
- a interface mostrou `Robô ligado.` e o servidor registrou `POST /api/robot/restart` com HTTP `200 OK`.

Falha já entendida:

- `abrir google.com e pesquisar inteligencia artificial` foi interpretado pelo planner determinístico como uma única URL inválida;
- isso confirma o limite atual de uma ação por comando, não uma falha de rede.

Uma tarefa antiga `capturar tela` aparece como `failed` no histórico; ela ocorreu antes da validação atual do Robô reiniciado com Desktop habilitado e não conta como validação final da captura.

Ainda precisam ser validados fisicamente pelo Painel:

- captura real de screenshot após o reinício atual;
- leitura da janela ativa;
- mouse;
- teclado;
- abertura de aplicativo permitido;
- diagnóstico pelo botão do Painel;
- `FAILSAFE` físico;
- parada de emergência real pelo Painel;
- ligar/parar Central e Robô pelo Painel em sequência completa.

## Ainda não implementado

- árvore de acessibilidade;
- percepção semântica de screenshots;
- controle genérico de arquivos;
- câmera;
- planner conectado a IA real;
- loop autônomo multietapa orientado a objetivo;
- confirmação humana completa para ações sensíveis;
- Central/Painel publicados para Internet;
- TLS, pareamento e autenticação forte para acesso remoto;
- WhatsApp;
- Telegram;
- Instagram.

## Limite operacional atual

Painel e Central escutam apenas localhost por padrão e não devem ser expostos diretamente à Internet nesta versão.

O sistema não oferece shell remoto arbitrário, não contorna login/MFA e não armazena credenciais no Git ou no planner.
