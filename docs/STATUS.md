# STATUS

## Objetivo atual

Construir um agente autônomo capaz de operar o computador do usuário como um operador digital, sempre dentro das permissões concedidas pelo usuário e pelo sistema operacional.

O objetivo final continua incluindo:

- mouse e teclado;
- aplicativos;
- navegador e sites;
- sessões autenticadas sem expor credenciais ao modelo;
- percepção da tela;
- câmera quando explicitamente autorizada;
- tarefas compostas em vários passos;
- controle remoto por Web, WhatsApp, Telegram e Instagram.

## Estado verificável agora

O branch `main` contém um MVP 0.2 funcional em código, com núcleo Web, navegador e primeiro slice de desktop implementados.

### Nomes e comandos visíveis

A interface de uso foi simplificada para reduzir ambiguidade durante o aprendizado:

- **Central** = processo servidor anteriormente chamado de `Control Plane`;
- **Robô local** = processo executor anteriormente chamado de `local agent`;
- o painel Web passa a exibir o título **Central do Robô**;
- `central` liga a Central;
- `robo` liga o Robô local;
- `parar-robo` controla a parada de emergência;
- `diagnostico-robo` executa o diagnóstico local.

Os comandos técnicos antigos continuam disponíveis como aliases de compatibilidade.

### Central e tarefas

- FastAPI com painel Web local;
- autenticação separada para usuário e Robô;
- SQLite como fila e histórico;
- polling HTTP autenticado;
- estados `queued`, `running`, `succeeded` e `failed`;
- leases de execução com token de propriedade;
- lease padrão de 120 segundos e máximo padrão de 3 tentativas;
- tarefa interrompida pode voltar para a fila após expiração do lease;
- resultado atrasado com lease antigo é recusado;
- após interrupções repetidas a tarefa falha em vez de entrar em loop infinito.

### Navegador

- Playwright + Chromium;
- comandos `abrir <site>` e `pesquisar/buscar <termo>`;
- verificação de URL final, título e status HTTP;
- bloqueio de localhost, `.local`, IPs privados/loopback e esquemas não HTTP(S).

### Desktop

Implementado em `src/context_anchor/desktop.py` com backend PyAutoGUI carregado apenas quando necessário.

Ações tipadas atuais:

- capturar screenshot;
- consultar janela ativa via `xdotool` quando disponível;
- mover mouse;
- clique esquerdo e direito;
- digitar texto limitado;
- pressionar teclas de uma allowlist;
- abrir aplicativos de uma allowlist fixa.

Allowlist inicial de aplicativos:

- Firefox;
- Chromium;
- Nemo/Nautilus;
- Xed/Gedit;
- VS Code;
- calculadora;
- LibreOffice.

Aplicativos são iniciados com `shell=False`; nome recebido remotamente não vira comando arbitrário.

O controle físico fica desativado por padrão por `CONTEXT_ANCHOR_DESKTOP_ENABLED=false`.

### Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py` e exposta principalmente por `parar-robo`.

- cria o marcador persistente `runtime/EMERGENCY_STOP` por padrão;
- Robô se recusa a iniciar enquanto o marcador existir;
- registra PID e tempo de início do processo Linux;
- verifica PID + identidade do processo antes de enviar `SIGTERM`;
- não depende de token do Robô nem do planner/modelo para funcionar;
- PyAutoGUI mantém `FAILSAFE` habilitado como proteção adicional.

### Diagnóstico local

Implementado comando `diagnostico-robo`.

Ele inspeciona sem controlar o computador:

- Python;
- sistema operacional;
- tipo de sessão gráfica;
- `DISPLAY`/Wayland;
- instalação do PyAutoGUI;
- `xdotool` e `scrot`;
- aplicativos da allowlist disponíveis.

### Planner

- planner determinístico continua ativo;
- criado contrato provider-agnostic em `src/context_anchor/planner.py`;
- saída estruturada só aceita ações tipadas conhecidas;
- campos extras e ação `shell` são rejeitados por esquema;
- Policy Layer continua sendo consultada depois do planner;
- nenhum provedor de IA foi ativado ainda.

## Validação automatizada

- workflow GitHub Actions instala dependências, compila o pacote e executa `pytest`;
- a primeira falha de integração do FastAPI encontrada anteriormente foi corrigida;
- CI do commit `8878d2e98a2475a723f47d42f032d8baeb271f19`, já contendo desktop, parada de emergência e leases, passou em instalação, compilação e testes;
- CI do commit `d9d473fe78494e7e56322bc592134f97db98501e`, incluindo o contrato de planner estruturado, também passou integralmente;
- a mudança atual de nomes adiciona aliases de CLI e altera textos visíveis, sem remover os comandos antigos. A validação do CI desta mudança deve ser confirmada após o workflow correspondente concluir.

## Validação física em andamento — Linux real

Resultados já confirmados no computador alvo:

- sessão gráfica `X11`;
- `DISPLAY=:0.0`;
- `WAYLAND_DISPLAY` vazio;
- `xdotool` disponível em `/usr/bin/xdotool`;
- `scrot` disponível em `/usr/bin/scrot` após instalação;
- Firefox disponível;
- Google Chrome detectado pelo id `chromium` da allowlist;
- Xed, VS Code, calculadora e LibreOffice disponíveis;
- Central iniciou corretamente em `127.0.0.1:8000`;
- Robô local iniciou e manteve polling HTTP autenticado com respostas `204 No Content` enquanto não havia tarefas;
- uma tarefa enviada pelo painel foi reivindicada pelo Robô e abriu uma janela Chromium real via Playwright;
- o comando único `abrir example.com` foi executado fisicamente com sucesso: o Chromium abriu `example.com`, exibiu `Example Domain` e o Robô reportou o resultado à Central com HTTP 200;
- o comando único `pesquisar inteligência artificial` foi executado fisicamente com sucesso: o Chromium abriu uma pesquisa no DuckDuckGo, o painel mostrou `status: succeeded`, `http_status: 200` e `verified: true`.

Falha física observada e explicada:

- o comando composto `abrir google.com e pesquisar inteligencia artificial` falhou com `ERR_NAME_NOT_RESOLVED`;
- o planner determinístico atual aceita uma ação por comando e interpretou todo o texto após `abrir` como um único endereço, produzindo uma URL inválida;
- isso demonstrou o limite atual do planner determinístico para comandos compostos, não falha de rede ou navegador.

Ainda precisam ser confirmados no computador alvo:

- novos aliases `central`, `robo`, `parar-robo` e `diagnostico-robo` após reinstalação editável;
- captura real de screenshot;
- leitura da janela ativa;
- movimento e clique do mouse;
- digitação e teclas;
- abertura dos aplicativos instalados;
- comportamento do `FAILSAFE`;
- parada de emergência encerrando o processo real.

## Ainda não implementado

- árvore de acessibilidade;
- percepção semântica de screenshots;
- controle genérico de arquivos;
- câmera;
- planner conectado a um modelo de IA real;
- loop autônomo de múltiplas ações orientado a objetivo;
- confirmação humana para ações sensíveis;
- Central publicada para Internet;
- TLS, pareamento de dispositivo e autenticação forte para acesso remoto;
- WhatsApp;
- Telegram;
- Instagram.

## Limite operacional atual

A Central escuta `127.0.0.1` por padrão e não deve ser exposta diretamente à Internet nesta versão.

O sistema não oferece shell arbitrário, não contorna login/MFA e não armazena credenciais no Git ou no planner.
