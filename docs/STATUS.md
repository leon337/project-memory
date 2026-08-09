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
- navegador com Playwright/Chromium;
- diagnóstico de Python, X11, PyAutoGUI, `xdotool`, `scrot` e Desktop;
- telemetria real de Painel, Central e Robô;
- Laboratório para comando conhecido e desconhecido sem execução de shell arbitrário.

## Segurança física e operacional

O backend de desktop em `src/context_anchor/desktop.py` mantém `pyautogui.FAILSAFE = True` e também uma proteção própria: antes de mover, clicar, digitar ou pressionar tecla, verifica se o ponteiro está dentro de uma zona de 20 pixels em qualquer canto da tela. Nesse caso a ação é recusada com `DesktopFailsafeTriggered`.

A parada de emergência em `src/context_anchor/emergency_stop.py` é independente do planner, usa estado persistente e impede reinício até liberação consciente.

Central, Painel e Robô continuam locais por padrão e não devem ser expostos diretamente à Internet nesta versão.

## Planner e roteador multi-provider

Foi implementada no `main` a primeira versão do modo **multi-provider**:

- `MultiProviderPlanner` em `src/context_anchor/planner.py`;
- adaptadores em `src/context_anchor/providers.py` para **Z.AI**, **Cloudflare Workers AI** e **Gemini**;
- configuração em `LocalAgentSettings` para modo do planner, timeout, cooldown, modelos e credenciais locais;
- `local_agent.py` constrói dinamicamente o roteador usando somente provedores configurados no `.env`;
- comandos que o planner determinístico já entende continuam sendo resolvidos localmente antes da IA, sem consumir quota externa;
- pedidos simples priorizam Cloudflare → Z.AI → Gemini quando esses provedores estiverem disponíveis;
- pedidos com marcadores de análise/condição priorizam Z.AI → Gemini → Cloudflare;
- falha de um provedor pode acionar outro provedor antes da execução física;
- toda saída continua validada como `StructuredAction` e depois passa pela Policy Layer.

## Primeiro teste real do planner multi-provider

Em 2026-08-09 foi feito o primeiro teste físico com `CONTEXT_ANCHOR_PLANNER_MODE=multi` e provedores **Z.AI + Gemini** configurados localmente.

Pedido enviado pelo Painel:

`Por favor abra o editor de texto para mim`

Resultado observado:

- o Robô iniciou em `planner=multi` com `providers=zai,gemini`;
- a tarefa entrou na Central e foi entregue normalmente ao Robô;
- **Z.AI respondeu HTTP 429**;
- o roteador tentou o fallback para **Gemini**;
- **Gemini respondeu HTTP 400**;
- a tarefa terminou `failed`;
- nenhuma ação física foi executada, portanto o fallback ocorreu antes da execução, como projetado.

Esse teste comprovou a cadeia básica de fallback, mas ainda não comprovou uma geração de plano bem-sucedida por API real.

## Correções após o primeiro teste real

O erro Gemini `HTTP 400` foi diagnosticado como incompatibilidade no corpo enviado ao endpoint `generateContent`. O adaptador foi corrigido no `main` para usar:

- `responseMimeType=application/json`;
- `responseJsonSchema=ACTION_SCHEMA`.

Também foi melhorado o diagnóstico HTTP dos provedores. Em respostas de erro, o sistema agora tenta registrar somente código/status e mensagem do provedor, sem copiar chave, headers de autenticação ou corpo da requisição.

O commit de testes dessa correção (`8769e23cf595f30fdb6c1943dbe4e79217d584e8`) teve CI `success` no run `31299282874`.

O `429` do Z.AI ainda não teve a causa específica confirmada. O endpoint, o model id `glm-4.7-flash` e o uso de `response_format={"type":"json_object"}` permanecem compatíveis com a documentação atual; o próximo teste deve revelar a mensagem real devolvida pela API.

## Provedores e credenciais — estado atual

- **Z.AI / `glm-4.7-flash`**: conta e API key criadas; tela real de Rate Limits mostrou `concurrency limit = 1`; chave configurada localmente no `.env`;
- **Google Gemini / `gemini-3.5-flash`**: chave configurada localmente no `.env`;
- **Cloudflare Workers AI**: token personalizado com Workers AI Read/Edit criado e guardado localmente; ainda falta `Account ID` no `.env` para ativar o adaptador;
- **SiliconFlow**: conta e API key criadas, mas permanece opcional enquanto um modelo gratuito atual e seus limites reais não forem comprovados.

As credenciais permanecem fora do Git. O usuário optou por continuar os testes com as chaves atuais.

## Próximo bloqueio real

O próximo bloqueio é revalidar o planner real depois da correção Gemini:

- atualizar a cópia local com `git pull --ff-only`;
- reiniciar o Robô pelo Painel;
- repetir a intenção em linguagem natural;
- confirmar se Gemini agora produz uma `StructuredAction` válida ou, se Z.AI continuar em `429`, capturar a mensagem específica do provedor;
- depois obter/configurar o `Cloudflare Account ID` e ativar o terceiro provedor.

## Ainda não implementado ou não validado

- uma geração de plano bem-sucedida por API real no Linux alvo;
- Cloudflare ativo no router real;
- quota manager completo com TPD/budget diário e telemetria detalhada por provedor;
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
