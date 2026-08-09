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

Feedback de uso real: o tema atual, predominantemente claro, foi considerado cansativo para a visão durante uso prolongado. A interface ainda precisa de revisão visual com menor luminosidade e melhor conforto antes de ser considerada pronta para uso diário.

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

A sincronização de foco foi reforçada e validada fisicamente:

- ao abrir aplicativo, o backend espera a janela ativa mudar em vez de confiar apenas em um `sleep` curto;
- a janela que recebeu foco é registrada como alvo esperado para teclado;
- digitação e tecla recusam execução se o foco mudou para outra janela;
- clique atualiza a janela esperada e pode confirmar novo foco;
- resultados de teclado registram id e título da janela ativa.

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
- tarefa `janela ativa` concluída como **`succeeded`**, validando a consulta da janela ativa via `xdotool`;
- movimento físico do mouse validado pelo Painel;
- clique físico validado visualmente ao minimizar uma janela;
- abertura de aplicativo permitida validada fisicamente com o Xed;
- capacidade física de digitação validada: o Xed recebeu o texto `teste do robo`;
- o encadeamento direto `abrir aplicativo editor` → `digitar teste do robo` foi repetido após a correção de foco, sem movimento do mouse nem clique intermediário, e funcionou corretamente;
- as duas tarefas do reteste foram registradas como **`succeeded`**, com o texto aparecendo no Xed.

## Falhas já diagnosticadas

- screenshot falhava inicialmente por ausência de `PIL`; corrigido com Pillow;
- processo zumbi era tratado como Robô online; corrigido verificando estado `Z`;
- comando composto `abrir google.com e pesquisar inteligencia artificial` excede o limite atual do planner determinístico de uma ação por comando;
- o primeiro encadeamento `abrir aplicativo editor` → `digitar teste do robo` marcou as duas tarefas como `succeeded`, mas o editor inicialmente permaneceu sem o texto esperado;
- um segundo encadeamento funcionou quando uma ação intermediária adicionou tempo antes da digitação, revelando uma condição de corrida de prontidão/foco;
- a condição de corrida foi corrigida com espera observável de foco e proteção de teclado e depois validada fisicamente em novo reteste direto.

## Correção validada

- `src/context_anchor/desktop.py` espera foco observável e protege teclado contra mudança de janela;
- `tests/test_desktop_focus.py` cobre rastreamento da janela focada, recusa de digitação quando o foco muda, registro da janela de destino e atualização de foco por clique;
- o CI do commit de testes concluiu com **success**;
- o computador alvo recebeu a correção por `git pull`, o Robô foi reiniciado e o reteste físico direto passou.

## Ainda precisa de validação física

- teclas permitidas;
- diagnóstico pelo botão do Painel;
- `FAILSAFE` físico;
- parada de emergência real pelo Painel;
- ciclo completo de ligar/parar/reiniciar Central e Robô sem depender de terminais manuais;
- Laboratório de comandos guiados no uso real;
- revisão visual do Painel com tema de menor luminosidade e validação do conforto visual no computador real.

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
