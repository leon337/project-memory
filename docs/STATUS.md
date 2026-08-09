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

### Direção de IA definida — multi-provider

A arquitetura do primeiro planner por IA será **multi-provider com roteamento inteligente consciente de quota**, e não dependente de um único serviço.

Conjunto inicial definido:

- **Z.AI / GLM-4.7-Flash** — reasoning e decisões mais complexas;
- **Cloudflare Workers AI** — decisões simples/frequentes e burst, preferindo modelos eficientes para preservar neurons;
- **Google Gemini** — multimodalidade/visão e fallback complementar.

O roteador não fará round-robin simples. A escolha deverá considerar capacidade exigida, quota/budget disponível, concorrência, latência, erros recentes e cooldown do provedor.

A pesquisa profunda de agosto de 2026 sustenta essa direção: GLM-4.7-Flash aparece com preço zero atual, reasoning, tools e structured output; Cloudflare possui 300 RPM default para text generation, mas é limitado também por 10.000 neurons/dia; Gemini continua relevante como provedor multimodal e complementar.

### Validação manual das contas

Confirmado no navegador:

- conta do **SiliconFlow** criada;
- API key do SiliconFlow criada para o projeto;
- tela **Usage & Charges** do SiliconFlow acessada sem consumo registrado (`$0.00`);
- o link **Higher Limits** do SiliconFlow abre um formulário de solicitação de aumento de RPM/TPM e não revela os limites atuais da conta;
- conta do **Z.AI** criada;
- API key do Z.AI criada para o projeto;
- a tela real **Rate Limits** do Z.AI foi acessada;
- para `GLM-4.7-Flash`, a conta mostrou **concurrency limit = 1**;
- a mesma tela mostra limites de concorrência diferentes por modelo, confirmando que o uso precisa respeitar o modelo escolhido;
- token personalizado do **Cloudflare Workers AI** criado com permissões **Workers AI: Read** e **Workers AI: Edit**;
- o token Cloudflare foi copiado e guardado localmente pelo usuário, sem ser enviado ao Git ou ao código;
- o token Cloudflare foi criado com escopo de recurso **Todas as contas**, que funciona, mas é mais amplo que o necessário e deve preferencialmente ser restringido à conta específica antes da integração;
- nenhuma chave de SiliconFlow, Z.AI ou Cloudflare foi adicionada ao Git ou integrada ao código.

SiliconFlow permanece candidato opcional futuro, mas não faz parte do conjunto inicial enquanto os limites reais de um modelo gratuito atual não forem comprovados.

## Próximo bloqueio real

Antes da integração multi-provider funcionar, ainda falta:

- restringir preferencialmente o token Cloudflare à conta específica e obter o `Account ID`;
- registrar os limites efetivos do projeto Gemini no AI Studio;
- implementar contabilidade local de quota/latência/erros para os provedores que não expõem telemetria suficiente;
- implementar o roteador e os adaptadores de Z.AI, Cloudflare e Gemini sobre o contrato provider-agnostic existente.

## Ainda não implementado

- planner conectado a IA real;
- roteador multi-provider;
- fallback automático entre provedores;
- quota manager;
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