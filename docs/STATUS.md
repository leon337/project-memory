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

## Planner e roteador multi-provider

O `DeterministicPlanner` continua sendo o modo padrão enquanto `CONTEXT_ANCHOR_PLANNER_MODE=deterministic`.

Foi implementada no `main` a primeira versão do modo **multi-provider**:

- `MultiProviderPlanner` em `src/context_anchor/planner.py`;
- adaptadores reais em `src/context_anchor/providers.py` para **Z.AI**, **Cloudflare Workers AI** e **Gemini**;
- configuração em `LocalAgentSettings` para modo do planner, timeout, cooldown, modelos e credenciais locais;
- `local_agent.py` constrói dinamicamente o roteador usando somente provedores que possuam credenciais suficientes no `.env`;
- comandos que o planner determinístico já entende continuam sendo resolvidos localmente antes da IA, sem consumir quota externa;
- pedidos simples priorizam Cloudflare → Z.AI → Gemini;
- pedidos com marcadores de análise/condição priorizam Z.AI → Gemini → Cloudflare;
- o roteador acompanha sucessos, falhas consecutivas, latência, cooldown e uma janela local de RPM quando há limite configurado;
- falha ou resposta estruturada inválida de um provedor pode acionar outro provedor **antes da execução física**;
- resultado de tarefa pode registrar `planner_provider`, `planner_route` e provedores que falharam sem registrar credenciais;
- toda saída ainda é validada como `StructuredAction` e depois passa pela Policy Layer.

O modo multi-provider **ainda não foi validado fisicamente com as chaves reais no computador do usuário**.

### Provedores iniciais

- **Z.AI / `glm-4.7-flash`** — principal para reasoning/decisões complexas;
- **Cloudflare Workers AI / `@cf/meta/llama-3.1-8b-instruct-fast`** — fast planner estruturado para chamadas simples;
- **Google Gemini / `gemini-3.5-flash`** — fallback textual inicial e base para multimodalidade futura.

A visão/multimodalidade do Gemini ainda não está conectada ao planner atual; o adaptador implementado nesta etapa recebe texto e devolve uma única `StructuredAction`.

## Contas e credenciais — estado real

Confirmado no navegador:

- conta e API key do **Z.AI** criadas;
- `GLM-4.7-Flash` mostrou **concurrency limit = 1** na tela real de Rate Limits;
- conta e API key do **SiliconFlow** criadas, mas o serviço permanece opcional enquanto o limite de um modelo free atual não for comprovado;
- token personalizado do **Cloudflare Workers AI** criado com permissões Workers AI Read/Edit e guardado localmente;
- Google/Gemini já possui chave disponível para o usuário;
- nenhuma chave foi gravada no Git.

Ainda falta obter/configurar localmente o **Cloudflare Account ID** para que o adaptador Cloudflare possa chamar a REST API.

## Testes automatizados desta etapa

Foram adicionados testes para:

- preservar comandos determinísticos sem chamada externa;
- roteamento fast para Cloudflare;
- roteamento de reasoning para Z.AI;
- fallback quando o primeiro provedor falha;
- fallback quando um provedor devolve ação estruturada inválida;
- parsing dos formatos de resposta de Z.AI, Cloudflare e Gemini sem acessar a rede;
- preservação de `Retry-After` em erro 429.

O commit de testes do roteador (`72596186a9038af5bcfe1ded23fb57254d9e73ed`) teve CI `success`. O commit de testes dos adaptadores (`4d4f32b39efd16860d34c385f8a305de9f069064`) também teve CI `success` no run `31298563811`.

## Próximo bloqueio real

O próximo bloqueio não é mais desenhar o router; é **ativá-lo no Linux real**:

- atualizar a cópia local com `git pull --ff-only`;
- colocar as chaves Z.AI e Gemini no `.env` e mudar `CONTEXT_ANCHOR_PLANNER_MODE=multi`;
- reiniciar o Robô e validar uma intenção simples em linguagem natural;
- depois adicionar `CLOUDFLARE_ACCOUNT_ID` ao `.env` e validar que uma intenção simples pode usar Cloudflare e fazer fallback para outro provedor.

## Ainda não implementado ou não validado

- validação física do planner multi-provider com APIs reais;
- quota manager completo com TPD/budget diário de Cloudflare e quotas desconhecidas do Z.AI;
- visão/multimodalidade ligada ao router;
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
