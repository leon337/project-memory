# STATUS

## Objetivo atual

Construir um operador digital local capaz de usar navegador e desktop dentro das permissões concedidas pelo usuário e pelo sistema operacional.

## Estado verificável agora

O branch `main` contém o **MVP 0.3** em código, com três processos separados:

- **Painel do Robô** — interface local de operação e aprendizado;
- **Central** — recebe, persiste e distribui tarefas;
- **Robô local** — executa ações permitidas no computador.

## Painel do Robô

Implementado em `src/context_anchor/dashboard.py`, iniciado por `painel-robo` e, por padrão, disponível apenas em `127.0.0.1:8765`.

O Painel mostra o estado de Central, Robô, Desktop e emergência; permite ligar/parar Central, ligar/parar/reiniciar Robô, alterar a habilitação do Desktop, executar diagnóstico, ver tarefas recentes, enviar tarefas e usar o Laboratório de comandos guiados.

O Laboratório não oferece shell arbitrário.

## Gerenciamento de processos

Implementado em `src/context_anchor/process_registry.py`.

- registros guardam PID e tempo de início do processo;
- a identidade é verificada antes de encerrar processos;
- processos Linux em estado `Z` (zumbi) são considerados desligados.

Essa correção resolveu o caso em que o Painel mostrava o Robô como ligado mesmo sem ele executar tarefas.

## Desktop

Implementado em `src/context_anchor/desktop.py` com ações tipadas para:

- capturar screenshot;
- consultar janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo e direito;
- digitar texto limitado;
- pressionar teclas permitidas;
- abrir aplicativos de allowlist fixa.

`Pillow` é dependência explícita porque o caminho de screenshot usa `PIL` por meio de `pyscreeze`.

## Navegador

- Playwright + Chromium;
- comandos `abrir <site>` e `pesquisar/buscar <termo>`;
- validação de URL e bloqueios locais do MVP.

## Planner

O `DeterministicPlanner` continua ativo. Existe contrato provider-agnostic em `src/context_anchor/planner.py`, mas nenhum provedor de IA real está conectado ainda.

## Validação física — Linux real

Confirmado no computador alvo:

- sessão X11 com `DISPLAY=:0.0`;
- `xdotool` e `scrot` instalados;
- Central em `127.0.0.1:8000` funcionando;
- Robô fazendo polling quando ligado;
- `abrir example.com` concluído com sucesso;
- `pesquisar inteligência artificial` concluído com sucesso;
- `.env` local com `CONTEXT_ANCHOR_DESKTOP_ENABLED=true`;
- Painel funcionando em `127.0.0.1:8765`;
- atalho `/home/leo/Área de trabalho/Painel do Robo.desktop` inicia o Painel;
- correção de processo zumbi validada fisicamente;
- botão **Ligar Robô** inicia uma nova execução funcional;
- Pillow `12.3.0` instalado na `.venv`;
- tarefas `capturar tela` concluíram como **`succeeded`**;
- tarefa `janela ativa` concluída como **`succeeded`**, validando a consulta da janela ativa via `xdotool`.

## Falhas já diagnosticadas

- screenshot falhava inicialmente por ausência de `PIL`; corrigido com Pillow;
- processo zumbi era tratado como Robô online; corrigido verificando estado `Z`;
- comando composto `abrir google.com e pesquisar inteligencia artificial` excede o limite atual do planner determinístico de uma ação por comando.

## Ainda precisa de validação física

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
- publicação segura do Painel/Central para acesso remoto;
- WhatsApp;
- Telegram;
- Instagram.

## Limite operacional atual

Painel e Central escutam apenas localhost por padrão e não devem ser expostos diretamente à Internet nesta versão.
