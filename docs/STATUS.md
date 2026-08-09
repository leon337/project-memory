# STATUS

## Objetivo atual

Construir um operador digital local capaz de usar navegador e desktop dentro das permissões concedidas pelo usuário e pelo sistema operacional, evoluindo depois para planejamento por IA, autonomia multietapa e acesso remoto seguro.

## Estado verificável agora

O branch `main` contém o **MVP 0.3** com três processos separados:

- **Painel do Robô** — interface local de operação, configuração, diagnóstico e aprendizado em `127.0.0.1:8765`;
- **Central** — recebe, persiste e distribui tarefas em `127.0.0.1:8000`;
- **Robô local** — consulta a fila, valida ações e executa capacidades permitidas no computador.

O fluxo físico principal do MVP 0.3 foi validado no Linux/X11 real.

## Painel do Robô

Implementado em `src/context_anchor/dashboard.py` e iniciado por `painel-robo`.

O Painel mostra estado real, configuração, diagnóstico, fila, telemetria e controles locais. A revisão atual usa tema ultra escuro e controles orientados por estado.

Validado fisicamente:

- Central distingue **Desligada**, **Ligada e gerenciada pelo Painel** e **Ligada fora do Painel**;
- Robô mostra estados **Ligado**, **Desligado** e bloqueado por emergência;
- emergência alterna corretamente entre **NORMAL** e **ATIVA**;
- tarefas recentes diferenciam `queued`, `running`, `succeeded` e `failed`;
- logs reais de Painel, Central e Robô aparecem separados por origem;
- Central e Robô podem ser iniciados, parados e reiniciados pelo Painel;
- o atalho local `Painel do Robo.desktop` inicia o Painel;
- Configurações e Laboratório renderizam e permanecem funcionais.

A revisão estética final do tema não foi formalmente encerrada como aprovada; operacionalmente a interface atual foi usada durante toda a validação física.

## Telemetria real

Implementada em `src/context_anchor/runtime_log.py`.

Arquivos estruturados:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Os componentes gravam timestamp, nível e eventos operacionais. Credenciais não são registradas e o logger estruturado não copia o texto bruto das tarefas.

Quando o Painel inicia Central ou Robô, `stdout/stderr` bruto fica separado em `central-process.log` e `robot-process.log`.

## Gerenciamento de processos

Implementado em `src/context_anchor/process_registry.py`.

- registros guardam PID e tempo de início do processo;
- a identidade é verificada antes de encerrar processos;
- processos Linux em estado `Z` são considerados desligados.

A correção para processo zumbi foi validada fisicamente.

## Desktop

Implementado em `src/context_anchor/desktop.py` com ações tipadas para:

- screenshot;
- janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo e direito;
- digitar texto limitado;
- pressionar teclas permitidas;
- abrir aplicativos de allowlist fixa.

`Pillow` é dependência explícita para screenshot.

A sincronização de foco foi reforçada e validada fisicamente: abrir aplicativo seguido de digitação funciona, e o teclado recusa execução quando o foco observado não corresponde ao alvo esperado.

### FAILSAFE explícito

O FAILSAFE nativo do PyAutoGUI falhou no primeiro teste real: com o ponteiro no canto superior esquerdo, `mover mouse 200 200` ainda foi executado.

Foi implementada proteção própria:

- `pyautogui.FAILSAFE = True` permanece como defesa adicional;
- antes de mover, clicar, digitar ou pressionar tecla, o backend verifica a posição atual do ponteiro;
- uma zona de 20 pixels nos quatro cantos dispara `DesktopFailsafeTriggered` antes de qualquer entrada física;
- testes automatizados cobrem os quatro cantos e as ações físicas.

Commits principais:

- `8bcc59c7c03be8671a437c5a5a996e8b0dd332f7` — proteção explícita;
- `634b1b70db94e8c00c86821f36032bd6d81129f5` — adaptação dos testes de foco;
- `4f398f4f745fbd996db13c710601fa83b3da5c37` — suíte específica do FAILSAFE.

O CI concluiu com **success** e a correção foi revalidada fisicamente em dois cantos: `mover mouse 200 200` terminou `failed` e os logs registraram `DesktopFailsafeTriggered` antes da entrada física.

## Navegador

- Playwright + Chromium;
- comandos atuais incluem `abrir <site>` e `pesquisar/buscar <termo>`;
- localhost, `.local`, IPs privados/loopback/link-local/reservados permanecem bloqueados no caminho de navegação do MVP.

Validação física concluída para `abrir example.com` e `pesquisar inteligência artificial`.

## Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py` com sentinel persistente e encerramento independente do planner.

Validada fisicamente em dois ciclos pelo Painel:

- ativação colocou emergência em **ATIVA**;
- o Robô foi encerrado e apareceu como **DESLIGADO**;
- início e reinício ficaram bloqueados durante a emergência;
- a liberação voltou para **NORMAL** sem reiniciar automaticamente;
- o Robô voltou a **LIGADO** somente após ação humana explícita;
- logs registraram ativação, liberação, solicitação de início, novo PID e inicialização.

## Ciclo operacional normal

Validado integralmente pelo Painel, sem terminal e sem emergência:

**Parar Robô → Desligado → Ligar Robô → Ligado**.

Os logs registraram solicitação de parada, sinal de parada, novo início e novo PID.

## Laboratório de comandos guiados

Validado fisicamente:

- `git pull`, que está catalogado, foi reconhecido e apenas explicado;
- a interface mostrou **O que faz**, **Por que usamos**, **Resultado esperado** e **Onde executar**;
- o comando não foi executado automaticamente;
- `git pull --ff-only`, não catalogado, também não foi executado e foi apresentado como comando desconhecido fora da execução automática.

Portanto, o Laboratório mantém o requisito de **não ser um shell remoto arbitrário**.

## Planner

O `DeterministicPlanner` continua ativo e é o único planner executando tarefas neste momento.

Existe contrato provider-agnostic em `src/context_anchor/planner.py` e saída estruturada `StructuredAction`.

A escolha vigente para a primeira integração real de IA é **Cerebras** com o modelo **`gpt-oss-120b`**, registrada em `DECISIONS.md` como D-026.

Estado atual da integração:

- provedor/modelo escolhidos;
- chave de API ainda não configurada no projeto;
- Cerebras ainda não está conectado ao código;
- nenhuma tarefa real está sendo planejada por IA ainda;
- Google/Gemini permanece disponível fora dessa integração e poderá ser considerado como fallback futuro;
- o contrato continua provider-agnostic para permitir troca de provedor sem alterar a Policy Layer ou os executores.

Uma pesquisa paralela por provedores gratuitos com limites maiores pode levar a uma revisão explícita da escolha, mas até nova decisão registrada o alvo vigente é Cerebras + `gpt-oss-120b`.

## Validação física consolidada — Linux real

Confirmado no computador alvo:

- sessão X11 com `DISPLAY=:0.0`;
- `xdotool` e `scrot` instalados;
- Central e Robô operacionais;
- navegador real validado;
- Desktop habilitado por `.env`;
- screenshot, mouse, clique, Xed, digitação e tecla Enter validados;
- proteção de foco validada;
- diagnóstico mostrou OK para Python, X11, PyAutoGUI, `xdotool`, `scrot` e Desktop;
- controles de estado e telemetria real validados;
- FAILSAFE explícito validado em dois cantos;
- parada de emergência validada em dois ciclos;
- ciclo normal parar/ligar Robô validado;
- Laboratório validado para comando conhecido e desconhecido sem execução automática.

## Falhas já diagnosticadas

- screenshot falhava por ausência de `PIL`; corrigido com Pillow;
- processo zumbi era tratado como Robô online; corrigido verificando estado `Z`;
- comando composto `abrir google.com e pesquisar inteligencia artificial` excede o limite atual do planner determinístico de uma ação por comando;
- abrir editor → digitar revelou condição de corrida de prontidão/foco; corrigida e validada;
- controles antigos não refletiam estado real; corrigidos e validados;
- logs anteriores dependiam dos processos terem sido iniciados pelo Painel; substituídos por telemetria estruturada;
- FAILSAFE nativo do PyAutoGUI não interrompeu a ação física; a proteção explícita própria corrigiu o problema e foi validada.

## Ainda não implementado

- integração de Cerebras/`gpt-oss-120b` ao planner;
- fallback multi-provider;
- loop autônomo multietapa orientado a objetivo;
- árvore de acessibilidade;
- percepção semântica de screenshots;
- controle genérico de arquivos;
- câmera;
- confirmação humana completa para ações sensíveis;
- publicação segura do Painel/Central para acesso remoto;
- WhatsApp;
- Telegram;
- Instagram;
- seletor claro/escuro e preferências visuais persistentes.

## Limite operacional atual

Painel e Central escutam apenas localhost por padrão e **não devem ser expostos diretamente à Internet** nesta versão.
