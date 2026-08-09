# STATUS

## Objetivo atual

Construir um operador digital local capaz de usar navegador e desktop dentro das permissões concedidas pelo usuário e pelo sistema operacional, evoluindo para planejamento por IA, autonomia multietapa e acesso remoto seguro.

## Estado verificável agora

O branch `main` contém o **MVP 0.3** com três processos separados:

- **Painel do Robô** — interface local de operação, configuração, diagnóstico e aprendizado em `127.0.0.1:8765`;
- **Central** — recebe, persiste e distribui tarefas em `127.0.0.1:8000`;
- **Robô local** — consulta a fila, valida ações e executa capacidades permitidas no computador.

O fluxo físico principal do MVP 0.3 foi validado no Linux/X11 real.

## Validação operacional concluída

Foram validados fisicamente no computador alvo:

- Central iniciada, parada e reconhecida corretamente pelo Painel;
- Robô iniciado, parado e reiniciado pelo Painel;
- ciclo normal **Parar Robô → Desligado → Ligar Robô → Ligado**;
- parada de emergência em dois ciclos reais, com bloqueio persistente e liberação consciente;
- FAILSAFE explícito em dois cantos da tela, gerando `DesktopFailsafeTriggered` antes da entrada física;
- screenshot, mouse, clique, Xed, digitação e tecla Enter;
- proteção de foco para sequências como abrir aplicativo → digitar;
- navegador com Playwright/Chromium para `abrir example.com` e `pesquisar inteligência artificial`;
- diagnóstico de Python, X11, PyAutoGUI, `xdotool`, `scrot` e Desktop;
- telemetria real de Painel, Central e Robô;
- Laboratório para comando conhecido e desconhecido sem execução de shell arbitrário.

## Segurança física e operacional

O backend de desktop em `src/context_anchor/desktop.py` mantém `pyautogui.FAILSAFE = True`, mas possui também proteção própria: antes de mover, clicar, digitar ou pressionar tecla, verifica se o ponteiro está dentro de uma zona de 20 pixels em qualquer canto da tela. Nesse caso a ação é recusada com `DesktopFailsafeTriggered`.

A parada de emergência em `src/context_anchor/emergency_stop.py` é independente do planner, usa estado persistente e impede reinício até liberação consciente.

A Central, o Painel e o Robô continuam locais por padrão e não devem ser expostos diretamente à Internet nesta versão.

## Telemetria e processos

Telemetria estruturada em:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Credenciais não são registradas e o logger estruturado evita copiar o texto bruto das tarefas.

O gerenciamento de processos em `src/context_anchor/process_registry.py` guarda PID e tempo de início e trata processos Linux em estado `Z` como desligados.

## Planner

O `DeterministicPlanner` continua ativo e é o único planner executando tarefas neste momento.

Existe contrato provider-agnostic em `src/context_anchor/planner.py`, com `StructuredAction` fechado para ações conhecidas e `ProviderPlanner` preparado para integração externa.

Nenhum provedor de IA real está integrado ao Robô ainda.

### Pesquisa de provedores — agosto de 2026

Uma pesquisa aprofundada sobre APIs gratuitas de IA mostrou que a escolha anterior por Cerebras não atende mais ao requisito atual de gratuidade recorrente: o serviço não possui mais um free tier renovável e a oferta atual é trial/crédito temporário.

Por isso, a seleção do primeiro provedor foi reaberta.

Candidatos principais em avaliação:

- **SiliconFlow**;
- **Z.AI / GLM**;
- **Cloudflare Workers AI**;
- **Groq**.

A pesquisa também identificou Cloudflare Workers AI como referência de 300 RPM default para text generation, sujeito a budget diário em neurons, e Groq como referência com limites gratuitos publicados por modelo. SiliconFlow e Z.AI permanecem candidatos prioritários porque os limites reais das contas/modelos gratuitos precisam ser medidos diretamente.

### Contas criadas nesta etapa

Confirmado por validação manual no navegador:

- conta do **SiliconFlow** criada;
- API key do SiliconFlow criada para o projeto;
- tela **Usage & Charges** do SiliconFlow acessada, ainda sem consumo registrado (`$0.00`);
- conta do **Z.AI** criada;
- API key do Z.AI criada para o projeto;
- nenhuma dessas chaves foi adicionada ao Git ou integrada ao código ainda.

As chaves devem permanecer somente em configuração local/variáveis de ambiente quando a integração começar.

## Próximo bloqueio real

Antes de integrar qualquer IA, ainda é necessário medir e confirmar:

- SiliconFlow: modelos realmente gratuitos, RPM/TPM/RPD/TPD e se a gratuidade é recorrente;
- Z.AI: limites reais dos modelos Flash/zero-price para a conta;
- comparar os resultados com Cloudflare Workers AI e Groq;
- escolher explicitamente o primeiro provedor/modelo.

## Ainda não implementado

- planner conectado a IA real;
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