# STATUS

## Objetivo atual

Construir um agente autônomo capaz de operar o computador do usuário como um operador digital, sempre dentro das permissões concedidas pelo usuário e pelo sistema operacional.

O objetivo final continua incluindo mouse, teclado, aplicativos, navegador, sites, sessões autenticadas, percepção da tela, câmera autorizada, tarefas compostas e controle remoto por Web, WhatsApp, Telegram e Instagram.

## Estado verificável agora

O branch `main` contém o **MVP 0.3** em código.

O projeto possui três processos com papéis separados:

- **Painel do Robô** — interface local de operação e aprendizado;
- **Central** — recebe, persiste e distribui tarefas;
- **Robô local** — executa ações permitidas no computador.

### Painel do Robô — implementado no MVP 0.3

Implementado em `src/context_anchor/dashboard.py` e iniciado pelo comando:

```text
painel-robo
```

Por padrão o Painel escuta somente `127.0.0.1:8765`.

Primeiro slice funcional:

- estado visual da Central;
- estado visual do Robô;
- estado de habilitação do Desktop;
- estado da parada de emergência;
- botões tipados para ligar/parar Central;
- botões tipados para ligar/parar/reiniciar Robô;
- controle visual para alterar `CONTEXT_ANCHOR_DESKTOP_ENABLED` no `.env`;
- indicação de que o Robô precisa ser reiniciado após mudança de configuração;
- diagnóstico local pela interface;
- fila com tarefas recentes;
- envio de tarefas do Robô sem digitar o token no navegador;
- logs separados de Central e Robô quando esses processos são iniciados pelo Painel;
- laboratório de comandos guiados com explicação de objetivo, motivo, resultado esperado e local de execução;
- layout responsivo com áreas Visão geral, Configurações e Laboratório.

O laboratório não possui endpoint genérico de shell. Comandos desconhecidos são explicados como não catalogados e não são executados automaticamente.

### Gerenciamento de processos — implementado

Criado `src/context_anchor/process_registry.py`.

- processos registrados guardam PID e tempo de início do Linux;
- antes de encerrar um processo, a identidade é verificada para reduzir risco de reutilização de PID;
- a Central passa a registrar `runtime/central.pid` quando iniciada pela versão nova;
- o Robô continua registrando `runtime/local_agent.pid`;
- o Painel consegue administrar processos iniciados/registrados pela versão nova;
- se detectar uma Central antiga iniciada fora do Painel, informa que ela precisa ser parada manualmente uma vez antes de passar a ser gerenciada pelo Painel.

### Nomes e comandos visíveis

Comandos humanos atuais:

- `painel-robo` — abre o gerenciador local;
- `central` — liga a Central;
- `robo` — liga o Robô;
- `parar-robo` — parada de emergência;
- `diagnostico-robo` — diagnóstico.

Os aliases técnicos antigos continuam disponíveis por compatibilidade.

### Central e tarefas

- FastAPI;
- autenticação separada para usuário e Robô;
- SQLite como fila e histórico;
- polling HTTP autenticado;
- estados `queued`, `running`, `succeeded` e `failed`;
- leases com token de propriedade;
- recuperação de tarefa interrompida;
- limite de tentativas;
- `TaskStore.list_recent()` adicionado para o Painel consultar tarefas recentes.

### Navegador

- Playwright + Chromium;
- comandos `abrir <site>` e `pesquisar/buscar <termo>`;
- verificação de URL final, título e status HTTP;
- bloqueio de localhost, `.local`, IPs privados/loopback e esquemas não HTTP(S).

### Desktop

Implementado em `src/context_anchor/desktop.py` com PyAutoGUI carregado somente quando necessário.

Ações tipadas atuais:

- capturar screenshot;
- consultar janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo e direito;
- digitar texto limitado;
- pressionar teclas permitidas;
- abrir aplicativos de allowlist fixa.

Aplicativos são iniciados com `shell=False`; nome recebido remotamente não vira comando arbitrário.

### Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py`.

- marcador persistente `runtime/EMERGENCY_STOP`;
- Robô se recusa a iniciar enquanto o marcador existir;
- PID + identidade de processo verificados antes de `SIGTERM`;
- independente do planner/modelo;
- PyAutoGUI mantém `FAILSAFE` habilitado.

### Diagnóstico

`diagnostico-robo` e o Painel consultam:

- Python;
- sistema operacional;
- sessão gráfica;
- `DISPLAY`/Wayland;
- PyAutoGUI;
- `xdotool`;
- `scrot`;
- aplicativos permitidos disponíveis.

### Planner

- planner determinístico continua ativo;
- contrato provider-agnostic em `src/context_anchor/planner.py`;
- saída estruturada aceita somente ações conhecidas;
- ação `shell` não existe no esquema;
- toda ação continua passando pela Policy Layer;
- nenhum provedor de IA real foi ativado ainda.

## Validação automatizada

- GitHub Actions instala dependências, compila e executa `pytest`;
- CI do commit `3bffd1bf8bca5093d399ce2f98b26a27eceadc48`, já contendo o Painel, seus endpoints tipados e testes do laboratório guiado, concluiu com sucesso;
- os testes verificam que não existe endpoint `/api/shell` genérico;
- testes anteriores de Central, desktop, emergency stop, planner, política e leases continuam no pipeline.

## Validação física — Linux real

Já confirmados no computador alvo:

- sessão `X11`;
- `DISPLAY=:0.0`;
- `xdotool` e `scrot` instalados;
- Firefox, Chrome/Chromium, Xed, VS Code, calculadora e LibreOffice detectados;
- Central em `127.0.0.1:8000` funcionando;
- Robô fazendo polling autenticado;
- `abrir example.com` concluído fisicamente com sucesso;
- `pesquisar inteligência artificial` concluído fisicamente com sucesso;
- `which central` encontrou o novo comando dentro da `.venv`;
- `which robo` encontrou o novo comando dentro da `.venv`;
- o `.env` local foi alterado durante a sessão de `CONTEXT_ANCHOR_DESKTOP_ENABLED=false` para `true`.

Falha já entendida:

- `abrir google.com e pesquisar inteligencia artificial` foi interpretado pelo planner determinístico como uma única URL inválida;
- isso confirma o limite atual de uma ação por comando, não uma falha do navegador ou da comunicação.

Ainda não validados fisicamente:

- `painel-robo` no computador alvo;
- controle de Central/Robô pelos botões do Painel;
- captura real de screenshot;
- leitura da janela ativa;
- mouse;
- teclado;
- abertura de aplicativo pelo executor de desktop;
- `FAILSAFE` físico;
- parada de emergência real pelo Painel.

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
