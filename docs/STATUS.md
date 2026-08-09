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

O Painel mostra o estado de Central, Robô, Desktop e emergência; permite ligar/parar Central, ligar/parar/reiniciar Robô, alterar a habilitação do Desktop, executar diagnóstico, ver tarefas recentes, enviar tarefas e usar o Laboratório de comandos guiados. O Laboratório não oferece shell arbitrário.

### Revisão visual

O tema claro original foi rejeitado em uso real por causar desconforto visual. A primeira revisão em dark mode melhorou a luminosidade, mas ainda foi considerada simples, com pouco contraste entre superfícies, textos secundários pequenos/apagados e espaço mal aproveitado.

O usuário definiu que, entre alternativas aceitáveis, **quanto mais escuro melhor**, desde que a leitura continue clara.

A segunda revisão visual ultra escura está implementada no `main` e foi carregada no computador alvo:

- tema `data-theme="ultra-dark"`;
- fundo principal próximo de preto (`#02050a`) e cards escuros (`#07101a`);
- tipografia e textos secundários com contraste maior;
- hierarquia visual reforçada nos títulos e seções;
- cards de status redesenhados;
- fila de tarefas com leitura mais clara;
- controles rápidos, comando e logs reorganizados;
- Configurações com layout específico para permissões, emergência e diagnóstico;
- Laboratório com dicas rápidas, fluxo visual e área de explicação mais estruturada;
- títulos/subtítulos específicos por tela;
- responsividade mantida.

Commits principais:

- `f885579181f3406e8719c816b243a049bdb1876c` — redesign ultra escuro;
- `1433a6884472da04ae6e88395e31028baffd7cb7` — testes do dashboard.

O CI concluiu com **success**. A nova versão foi baixada por `git pull`, o Painel foi reiniciado pelo atalho do desktop e as três telas **Visão geral**, **Configurações** e **Laboratório** foram confirmadas visualmente no computador real com a nova revisão carregada. Falta apenas a confirmação subjetiva final do usuário sobre conforto visual antes de encerrar essa revisão.

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

- ao abrir aplicativo, o backend espera a janela ativa mudar;
- a janela focada é registrada como alvo esperado para teclado;
- digitação e tecla recusam execução se o foco mudar para outra janela;
- clique atualiza a janela esperada;
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
- `capturar tela` concluído como `succeeded`;
- `janela ativa` concluída como `succeeded`;
- movimento físico do mouse validado;
- clique físico validado visualmente ao minimizar uma janela;
- abertura de aplicativo validada com o Xed;
- digitação física validada no Xed;
- encadeamento `abrir aplicativo editor` → `digitar teste do robo` validado após correção de foco;
- tecla **Enter** validada em sequência com duas linhas distintas no Xed;
- botão **Diagnóstico** mostrou OK para Python, X11, PyAutoGUI, `xdotool`, `scrot` e Desktop;
- primeira versão dark avaliada e rejeitada como ainda insuficiente;
- segunda revisão ultra escura carregada e visualmente confirmada nas telas Visão geral, Configurações e Laboratório.

## Falhas já diagnosticadas

- screenshot falhava por ausência de `PIL`; corrigido com Pillow;
- processo zumbi era tratado como Robô online; corrigido verificando estado `Z`;
- comando composto `abrir google.com e pesquisar inteligencia artificial` excede o limite atual do planner determinístico de uma ação por comando;
- primeira sequência abrir editor → digitar revelou condição de corrida de prontidão/foco; corrigida e validada;
- tema claro original causava desconforto visual; primeira revisão dark ainda foi insuficiente; segunda revisão ultra escura está carregada e aguarda apenas aprovação subjetiva final.

## Ainda precisa de validação física

- confirmar conforto visual final da segunda revisão ultra escura;
- `FAILSAFE` físico;
- parada de emergência real pelo Painel;
- ciclo completo de ligar/parar/reiniciar Central e Robô sem depender de terminais manuais;
- Laboratório de comandos guiados no uso real.

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
