# STATUS

## Objetivo atual

Construir um operador digital local capaz de usar navegador e desktop dentro das permissões concedidas pelo usuário e pelo sistema operacional.

O objetivo final continua incluindo sites, sessões autenticadas sem entregar credenciais ao modelo, mouse, teclado, aplicativos, percepção da tela, câmera autorizada, tarefas compostas e controle remoto futuro por Web, WhatsApp, Telegram e Instagram.

## Estado verificável agora

O branch `main` contém o **MVP 0.3** em código.

O sistema possui três processos separados:

- **Painel do Robô** — interface local de operação e aprendizado;
- **Central** — recebe, persiste e distribui tarefas;
- **Robô local** — executa ações permitidas no computador.

## Painel do Robô

Implementado em `src/context_anchor/dashboard.py` e iniciado por:

```text
painel-robo
```

Por padrão escuta somente `127.0.0.1:8765`.

Capacidades atuais:

- estado visual de Central, Robô, Desktop e emergência;
- ligar/parar Central;
- ligar/parar/reiniciar Robô;
- alterar `CONTEXT_ANCHOR_DESKTOP_ENABLED`;
- diagnóstico local;
- tarefas recentes;
- envio de tarefas sem digitar token no navegador;
- logs de Central e Robô quando gerenciados pelo Painel;
- Laboratório de comandos guiados;
- áreas Visão geral, Configurações e Laboratório.

O Laboratório não oferece shell arbitrário.

## Gerenciamento de processos

Implementado em `src/context_anchor/process_registry.py`.

- registros guardam PID e tempo de início do processo no Linux;
- a identidade é verificada antes de encerrar processos;
- a Central usa `runtime/central.pid`;
- o Robô usa `runtime/local_agent.pid`;
- processos Linux em estado `Z` (zumbi) são considerados desligados.

Essa correção resolveu o caso em que o Painel mostrava o Robô como ligado mesmo sem ele executar tarefas.

## Desktop

Implementado em `src/context_anchor/desktop.py`.

Ações tipadas atuais:

- capturar screenshot;
- consultar janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo e direito;
- digitar texto limitado;
- pressionar teclas permitidas;
- abrir aplicativos de allowlist fixa.

Aplicativos são iniciados com `shell=False`; nomes recebidos remotamente não viram comandos arbitrários.

`Pillow` passou a ser dependência explícita porque `pyscreeze` precisa de `PIL` para screenshots.

## Navegador

- Playwright + Chromium;
- comandos `abrir <site>` e `pesquisar/buscar <termo>`;
- verificação de URL final, título e status HTTP;
- bloqueio de localhost, `.local`, IPs privados/loopback e esquemas não HTTP(S).

## Planner

O `DeterministicPlanner` continua ativo.

Comandos suportados atualmente incluem:

- `capturar tela`;
- `janela ativa`;
- `mover mouse X Y`;
- `clicar` / `clique direito`;
- `digitar <texto>`;
- `tecla <tecla>`;
- `abrir aplicativo <app>`;
- `pesquisar <termo>`;
- `abrir <site>`.

Existe contrato provider-agnostic em `src/context_anchor/planner.py`, mas nenhum provedor de IA real está conectado ainda.

## Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py`.

- marcador persistente `runtime/EMERGENCY_STOP`;
- Robô não inicia enquanto o marcador existir;
- PID + identidade são verificados antes de `SIGTERM`;
- independente do planner/modelo;
- PyAutoGUI mantém `FAILSAFE` habilitado.

## Diagnóstico

`diagnostico-robo` e o Painel verificam Python, sistema, sessão gráfica, `DISPLAY`/Wayland, PyAutoGUI, Pillow/PIL, pyscreeze, `xdotool`, `scrot` e aplicativos permitidos.

## Validação automatizada

GitHub Actions instala dependências, compila e executa `pytest`.

Os testes cobrem Central, desktop, planner, política, leases, emergência, Painel, ausência de endpoint `/api/shell`, diagnóstico e detecção de processo zumbi.

## Validação física — Linux real

Confirmado no computador alvo:

- sessão `X11`;
- `DISPLAY=:0.0`;
- `xdotool` e `scrot` instalados;
- Firefox, Chrome/Chromium, Xed, VS Code, calculadora e LibreOffice detectados;
- Central em `127.0.0.1:8000` funcionando;
- Robô fazendo polling autenticado quando ligado;
- `abrir example.com` executado fisicamente com sucesso;
- `pesquisar inteligência artificial` executado fisicamente com sucesso;
- comandos `central`, `robo` e `painel-robo` instalados na `.venv`;
- `.env` local com `CONTEXT_ANCHOR_DESKTOP_ENABLED=true`;
- Painel funcionando em `127.0.0.1:8765`;
- Visão geral, Configurações e Laboratório funcionando;
- atalho `/home/leo/Área de trabalho/Painel do Robo.desktop` inicia o Painel;
- correção de processo zumbi puxada e validada fisicamente: o Painel passou a mostrar o Robô como **Desligado** quando o processo não estava executando trabalho;
- botão **Ligar Robô** iniciou uma nova execução e o cartão mudou para **Ligado**;
- Pillow `12.3.0` foi instalado dentro da `.venv`;
- duas tarefas `capturar tela` que estavam em `queued` foram buscadas pelo novo processo do Robô e terminaram como **`succeeded`**;
- isso confirma fisicamente que a captura de tela funciona após a correção de Pillow e do estado de processo.

## Falhas já diagnosticadas

- screenshot falhava inicialmente com `ModuleNotFoundError: No module named 'PIL'`; corrigido adicionando Pillow e reinstalando o projeto;
- o Painel tratava processo zumbi como Robô online; corrigido verificando o estado Linux `Z`;
- `abrir google.com e pesquisar inteligencia artificial` é interpretado como uma única URL inválida pelo planner determinístico; é um limite atual de uma ação por comando, não falha de rede.

## Ainda precisa de validação física

- `janela ativa`;
- movimento do mouse;
- clique do mouse;
- digitação;
- teclas permitidas;
- abertura de aplicativo permitido;
- diagnóstico pelo botão do Painel;
- `FAILSAFE` físico;
- parada de emergência real pelo Painel;
- ciclo completo de ligar/parar/reiniciar Central e Robô sem depender de terminais manuais.

## Ainda não implementado

- árvore de acessibilidade;
- percepção semântica de screenshots;
- controle genérico de arquivos;
- câmera;
- planner conectado a IA real;
- loop autônomo multietapa orientado a objetivo;
- confirmação humana completa para ações sensíveis;
- publicação segura da Central/Painel para Internet;
- TLS, pareamento e autenticação forte para acesso remoto;
- WhatsApp;
- Telegram;
- Instagram.

## Limite operacional atual

Painel e Central escutam apenas localhost por padrão e não devem ser expostos diretamente à Internet nesta versão.

O sistema não oferece shell remoto arbitrário, não contorna login/MFA e não armazena credenciais no Git ou no planner.
