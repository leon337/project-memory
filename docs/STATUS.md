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
- o Painel administra processos compatíveis com esses registros;
- a detecção em `main` agora consulta também o estado Linux do processo e considera estado `Z` (zumbi) como desligado, em vez de confiar apenas na existência do PID em `/proc`.

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

A dependência `Pillow` foi adicionada explicitamente ao `pyproject.toml` porque `pyscreeze` importa `PIL` para screenshots e a instalação anterior não trouxe esse módulo para a `.venv` do computador alvo.

## Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py`.

- marcador persistente `runtime/EMERGENCY_STOP`;
- Robô se recusa a iniciar enquanto o marcador existir;
- PID + identidade de processo verificados antes de `SIGTERM`;
- independente do planner/modelo;
- PyAutoGUI mantém `FAILSAFE` habilitado.

## Diagnóstico

`diagnostico-robo` e o Painel verificam Python, sistema, sessão gráfica, `DISPLAY`/Wayland, PyAutoGUI, `xdotool`, `scrot` e aplicativos permitidos.

O diagnóstico agora também informa se `Pillow (PIL)` e `pyscreeze` estão instalados, porque ambos participam do caminho de screenshot via PyAutoGUI.

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
- testes anteriores de Central, desktop, emergency stop, planner, política e leases continuam no pipeline;
- foi adicionado teste para os campos de diagnóstico de `Pillow` e `pyscreeze`;
- foram adicionados testes específicos para garantir que registros de processo em estado Linux `Z` não sejam tratados como Robô online; o CI correspondente ainda estava em execução na última verificação.

## Validação física — Linux real

Já confirmado no computador alvo:

- sessão `X11` e `DISPLAY=:0.0`;
- `xdotool` e `scrot` instalados;
- Firefox, Chrome/Chromium, Xed, VS Code, calculadora e LibreOffice detectados;
- Central em `127.0.0.1:8000` funcionando;
- Robô fez polling autenticado durante testes anteriores;
- `abrir example.com` executado fisicamente com sucesso;
- `pesquisar inteligência artificial` executado fisicamente com sucesso;
- comandos `central`, `robo` e `painel-robo` instalados dentro da `.venv`;
- `.env` local está com `CONTEXT_ANCHOR_DESKTOP_ENABLED=true`;
- `painel-robo` iniciou fisicamente em `127.0.0.1:8765`;
- Visão geral, Configurações e Laboratório abriram corretamente no navegador;
- o Painel detectou Central ligada, Robô ligado, Desktop habilitado e emergência normal;
- foi criado localmente um atalho `.desktop` em `/home/leo/Área de trabalho/Painel do Robo.desktop` e ele inicia o Painel;
- uma tarefa `capturar tela` chegou ao Robô e falhou inicialmente porque `Pillow/PIL` não estava instalado;
- a leitura direta da tarefa no SQLite mostrou `PyAutoGUIException: PyAutoGUI was unable to import pyscreeze`;
- o teste direto `python -c "import pyscreeze"` revelou `ModuleNotFoundError: No module named 'PIL'`;
- a correção de dependência foi puxada e `pip install -e .` instalou com sucesso `pillow-12.3.0` dentro da `.venv`.

Falhas observadas e diagnóstico atual:

- depois da instalação do Pillow, o botão **Reiniciar Robô** respondeu `O Robô já está online.` em vez de comprovar uma nova execução;
- o botão **Parar Robô** mostrou `Sinal de parada enviado para o Robô.`, mas o cartão permaneceu `Ligado` por vários minutos;
- ao tentar ligar novamente, o Painel respondeu `O Robô já está online.`;
- novas tarefas `capturar tela` permaneceram em `queued`, `aguardando Robô`, tentativa 0, mostrando que nenhum executor funcional estava buscando a fila;
- o comportamento é compatível com um processo encerrado em estado Linux zumbi ainda sendo considerado vivo porque a versão local antiga verificava somente PID + start ticks;
- `main` foi corrigido para rejeitar estado `Z` e limpar esse registro, mas essa correção ainda precisa ser puxada e o processo do Painel precisa ser reiniciado no computador alvo antes do reteste;
- `abrir google.com e pesquisar inteligencia artificial` continua documentado como limite do planner determinístico de uma ação por comando, não falha de rede.

Ainda precisam ser validados fisicamente pelo Painel:

- puxar a correção de detecção de processo zumbi e reiniciar o Painel;
- confirmar que **Parar Robô** muda o estado para desligado e **Ligar/Reiniciar Robô** inicia uma execução funcional;
- repetir `capturar tela` com Pillow instalado;
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
