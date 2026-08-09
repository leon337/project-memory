# STATUS

## Objetivo atual

Construir um operador digital local capaz de usar navegador e desktop dentro das permissões concedidas pelo usuário e pelo sistema operacional.

## Estado verificável agora

O branch `main` contém o **MVP 0.3** com três processos separados:

- **Painel do Robô** — interface local de operação e aprendizado;
- **Central** — recebe, persiste e distribui tarefas;
- **Robô local** — executa ações permitidas no computador.

## Painel do Robô

Implementado em `src/context_anchor/dashboard.py`, iniciado por `painel-robo` e disponível por padrão apenas em `127.0.0.1:8765`.

O Painel mostra estado, configuração, diagnóstico, fila, telemetria e controles locais. O Laboratório não oferece shell arbitrário.

### Revisão visual e operacional

O tema claro original foi rejeitado em uso real por causar desconforto visual. Uma primeira revisão dark melhorou a luminosidade, mas ainda foi considerada simples. A segunda revisão ultra escura foi carregada e confirmada fisicamente nas telas **Visão geral**, **Configurações** e **Laboratório**.

O usuário não encerrou a revisão visual como aprovada. Na avaliação seguinte apontou dois problemas funcionais de interface:

1. os antigos **Controles rápidos** disparavam ações, mas não permitiam entender pelo próprio controle o estado atual de Central/Robô/emergência;
2. a área **Logs ao vivo** não representava de forma confiável logs reais da aplicação quando os processos tinham sido iniciados fora do Painel.

Uma terceira revisão está implementada e já foi carregada fisicamente no computador alvo:

- fundo ainda mais escuro (`#010308`);
- **Controles de estado** para Central, Robô e Emergência;
- texto, cor e ação de cada controle mudam conforme `/api/status`;
- Central distingue **desligada**, **ligada e gerenciada** e **ligada fora do Painel**;
- quando a Central está ligada externamente, o Painel não finge possuir capacidade de parada e informa a situação;
- Robô bloqueado por emergência não oferece ação de início;
- emergência alterna visualmente entre estado **Normal** e **ATIVA**;
- tarefas recentes diferenciam `queued`, `running`, `succeeded` e `failed` em vez de usar sempre um ✓ verde;
- a área foi renomeada para **Logs reais da aplicação** e possui filtros **Todos / Painel / Central / Robô**.

Validação física desta revisão:

- **Central** apareceu inicialmente como **Ligada fora do Painel**, coerente com o fato de estar rodando em terminal separado;
- depois que a Central externa foi encerrada no terminal, o Painel atualizou automaticamente para **Desligada** e passou a oferecer apenas **Ligar Central**;
- a Central foi então iniciada pelo próprio Painel e passou a aparecer como **LIGADA — Em execução e gerenciada pelo Painel**, oferecendo **Parar Central**;
- **Robô local** aparece como **Ligado**, com ações **Parar Robô** e **Reiniciar** disponíveis;
- o Robô foi reiniciado pelo próprio Painel e voltou ao estado operacional, com os controles continuando coerentes;
- **Emergência** aparece como **Normal**, com a ação **Ativar emergência** disponível;
- as telas **Configurações** e **Laboratório** continuam renderizando corretamente após a revisão;
- a seção **Logs reais da aplicação** exibiu evento real do Painel com timestamp e origem `[PAINEL]` logo após sua inicialização;
- após iniciar a Central pelo Painel, a seção exibiu eventos reais separados de `[PAINEL]` e `[CENTRAL]`, incluindo solicitação de início, inicialização da Central em `127.0.0.1:8000` e registro do PID criado pelo Painel;
- após reiniciar o Robô pelo Painel, a seção exibiu a sequência real de solicitação de reinício, parada, novo início e eventos `[ROBÔ]` informando `agente=desktop-principal` e `desktop=habilitado`.

### Telemetria real

Foi criado `src/context_anchor/runtime_log.py`.

Painel, Central e Robô gravam eventos estruturados próprios em:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Cada evento possui timestamp com timezone, nível e mensagem operacional. Esses logs são produzidos pelo próprio componente, portanto não dependem de o processo ter sido iniciado pelo Painel.

Eventos estruturados registram ids de tarefas, estados, transições e erros. Credenciais não são registradas e o logger de runtime não copia o texto bruto das tarefas para o log.

Quando o Painel inicia Central ou Robô, `stdout/stderr` bruto é separado em `central-process.log` e `robot-process.log`.

Commits principais da rodada do Painel e telemetria:

- `2aec014c2c7e55570e818a748394ad044e77717f` — logger persistente de runtime;
- `4936badd931091d596a8036786090238916b2ca7` — eventos reais da Central;
- `5dfa6e685bc84885afb5dbe4c87497801bdeabc3` — eventos reais do Robô;
- `c7962d092625f60743cb50393833a2c0c247b3de` — controles orientados por estado e UI de logs reais;
- `823715419db91206dfac455b3af2b47c29b4b618` — testes do novo Painel;
- `fd5192628c7c1e6c4d3e58a00dbc09693265b4f2` — testes do logger de runtime.

O CI dessa rodada concluiu com **success**.

## Gerenciamento de processos

Implementado em `src/context_anchor/process_registry.py`.

- registros guardam PID e tempo de início do processo;
- a identidade é verificada antes de encerrar processos;
- processos Linux em estado `Z` (zumbi) são considerados desligados.

A correção de processo zumbi já foi validada fisicamente.

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

A sincronização de foco foi reforçada e validada fisicamente: abrir aplicativo seguido de digitação funciona sem atraso artificial intermediário, e teclado recusa execução quando o foco observado não corresponde ao alvo esperado.

### FAILSAFE explícito

A primeira validação física do FAILSAFE nativo do PyAutoGUI **falhou**: com o ponteiro colocado no canto superior esquerdo, a tarefa `mover mouse 200 200` foi marcada como `succeeded`, o ponteiro foi movido e a telemetria registrou execução com sucesso.

A correção foi implementada no `main`:

- `pyautogui.FAILSAFE = True` continua habilitado como defesa adicional;
- o backend verifica diretamente a posição atual do ponteiro antes de `move_mouse`, `click_mouse`, `type_text` e `press_key`;
- existe uma zona de segurança de 20 pixels nos quatro cantos da tela;
- quando o ponteiro está nessa zona, o backend levanta `DesktopFailsafeTriggered` antes de enviar qualquer entrada física;
- a exceção sobe pelo fluxo normal do Robô e faz a tarefa terminar como `failed`, com o tipo do erro registrado na telemetria;
- testes automatizados cobrem os quatro cantos, mouse, clique, digitação, tecla e execução normal fora da zona.

Commits desta correção:

- `8bcc59c7c03be8671a437c5a5a996e8b0dd332f7` — proteção explícita nos cantos;
- `634b1b70db94e8c00c86821f36032bd6d81129f5` — adaptação dos testes de foco;
- `4f398f4f745fbd996db13c710601fa83b3da5c37` — suíte específica do FAILSAFE.

O CI do commit `4f398f4f745fbd996db13c710601fa83b3da5c37` concluiu com **success**.

A correção foi **revalidada fisicamente no computador alvo em dois cantos da tela**. Em ambos os testes com `mover mouse 200 200`, a tarefa terminou como `failed` e a telemetria do Robô registrou `DesktopFailsafeTriggered` com a mensagem de que o ponteiro foi detectado na zona de segurança e a entrada física foi recusada antes da execução. Portanto, a proteção explícita cumpriu o critério físico que havia falhado com o FAILSAFE nativo do PyAutoGUI.

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
- movimento e clique físicos do mouse validados;
- abertura do Xed, digitação e tecla **Enter** validadas;
- encadeamento abrir editor → digitar validado após correção de foco;
- botão **Diagnóstico** mostrou OK para Python, X11, PyAutoGUI, `xdotool`, `scrot` e Desktop;
- segunda revisão ultra escura carregada e confirmada visualmente nas três telas;
- terceira revisão carregada e validada fisicamente para controles de estado;
- transição real da Central de **Ligada fora do Painel** → **Desligada** → **Ligada e gerenciada pelo Painel** refletida corretamente;
- telemetria real da Central validada fisicamente no Painel com eventos `[CENTRAL]` e `[PAINEL]` coerentes com a transição observada;
- reinício do Robô pelo Painel validado, com novo PID e retorno ao estado operacional;
- telemetria real do Robô validada fisicamente com eventos `[ROBÔ]` e `[PAINEL]` coerentes com a reinicialização;
- FAILSAFE explícito revalidado fisicamente em dois cantos: as duas tarefas `mover mouse 200 200` terminaram `failed` e os logs registraram `DesktopFailsafeTriggered` antes da entrada física.

## Falhas já diagnosticadas

- screenshot falhava por ausência de `PIL`; corrigido com Pillow;
- processo zumbi era tratado como Robô online; corrigido verificando estado `Z`;
- comando composto `abrir google.com e pesquisar inteligencia artificial` excede o limite atual do planner determinístico de uma ação por comando;
- primeira sequência abrir editor → digitar revelou condição de corrida de prontidão/foco; corrigida e validada;
- tema claro original causava desconforto visual; revisões dark foram aplicadas;
- controles rápidos anteriores não expressavam o estado real do componente; corrigido em código e validado fisicamente para Central, Robô e Emergência;
- logs anteriores dependiam excessivamente de processos iniciados pelo Painel; substituídos por telemetria estruturada. Logs reais de Painel, Central e Robô já foram validados fisicamente;
- FAILSAFE nativo do PyAutoGUI não interrompeu a ação física no primeiro teste real; foi substituído como proteção principal por uma verificação explícita própria nos cantos, que passou no CI e foi revalidada fisicamente em dois cantos.

## Ainda precisa de validação física

- validar parada de emergência real e liberação consciente;
- validar a transição explícita **Parar Robô → Desligado → Ligar Robô → Ligado** pelo Painel;
- testar o Laboratório com um comando conhecido;
- concluir o uso diário sem dependência normal de terminais separados.

## Ainda não implementado

- seletor claro/escuro e preferências visuais persistentes;
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
