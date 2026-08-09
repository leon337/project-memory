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

Uma terceira revisão já está implementada no `main`:

- fundo ainda mais escuro (`#010308`);
- **Controles de estado** para Central, Robô e Emergência;
- texto, cor e ação de cada controle mudam conforme `/api/status`;
- Central distingue **desligada**, **ligada e gerenciada** e **ligada fora do Painel**;
- quando a Central está ligada externamente, o Painel não finge possuir capacidade de parada e informa a situação;
- Robô bloqueado por emergência não oferece ação de início;
- emergência alterna visualmente entre estado **Normal** e **ATIVA**;
- tarefas recentes diferenciam `queued`, `running`, `succeeded` e `failed` em vez de usar sempre um ✓ verde;
- a área foi renomeada para **Logs reais da aplicação** e possui filtros **Todos / Painel / Central / Robô**.

### Telemetria real

Foi criado `src/context_anchor/runtime_log.py`.

Painel, Central e Robô agora gravam eventos estruturados próprios em:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Cada evento possui timestamp com timezone, nível e mensagem operacional. Esses logs são produzidos pelo próprio componente, portanto não dependem de o processo ter sido iniciado pelo Painel.

Eventos estruturados registram ids de tarefas, estados, transições e erros. Credenciais não são registradas e o logger de runtime não copia o texto bruto das tarefas para o log.

Quando o Painel inicia Central ou Robô, `stdout/stderr` bruto é separado em `central-process.log` e `robot-process.log`.

Commits principais desta rodada:

- `2aec014c2c7e55570e818a748394ad044e77717f` — logger persistente de runtime;
- `4936badd931091d596a8036786090238916b2ca7` — eventos reais da Central;
- `5dfa6e685bc84885afb5dbe4c87497801bdeabc3` — eventos reais do Robô;
- `c7962d092625f60743cb50393833a2c0c247b3de` — controles orientados por estado e UI de logs reais;
- `823715419db91206dfac455b3af2b47c29b4b618` — testes do novo Painel;
- `fd5192628c7c1e6c4d3e58a00dbc09693265b4f2` — testes do logger de runtime.

O CI do código desta rodada concluiu com **success**. A terceira revisão **ainda não foi puxada nem validada fisicamente no computador alvo**.

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
- segunda revisão ultra escura carregada e confirmada visualmente nas três telas.

## Falhas já diagnosticadas

- screenshot falhava por ausência de `PIL`; corrigido com Pillow;
- processo zumbi era tratado como Robô online; corrigido verificando estado `Z`;
- comando composto `abrir google.com e pesquisar inteligencia artificial` excede o limite atual do planner determinístico de uma ação por comando;
- primeira sequência abrir editor → digitar revelou condição de corrida de prontidão/foco; corrigida e validada;
- tema claro original causava desconforto visual; revisões dark foram aplicadas;
- controles rápidos anteriores não expressavam o estado real do componente; corrigido em código e aguardando validação física;
- logs anteriores dependiam excessivamente de processos iniciados pelo Painel; substituídos por telemetria estruturada produzida por cada componente e aguardando validação física.

## Ainda precisa de validação física

- puxar a terceira revisão e reiniciar o Painel;
- confirmar visualmente que **Controles de estado** refletem Central, Robô e Emergência corretamente;
- validar que a Central atualmente iniciada fora do Painel aparece explicitamente como externa, se esse ainda for o estado real;
- reiniciar Central e Robô com o código novo e confirmar eventos reais aparecendo nos filtros de log;
- validar `FAILSAFE` físico;
- validar parada de emergência real e liberação consciente;
- concluir ciclo completo de gerenciamento sem dependência normal de terminais.

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
