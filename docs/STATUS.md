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

## Testes reais do planner multi-provider

Em 2026-08-09 foi ativado `CONTEXT_ANCHOR_PLANNER_MODE=multi` no Linux real com provedores **Z.AI + Gemini** configurados localmente.

Pedido usado nos testes:

`Por favor abra o editor de texto para mim`

### Primeiro teste

Resultado observado:

- o Robô iniciou em `planner=multi` com `providers=zai,gemini`;
- a tarefa entrou na Central e foi entregue normalmente ao Robô;
- Z.AI respondeu `HTTP 429`;
- o roteador tentou Gemini;
- Gemini respondeu `HTTP 400` com o formato então usado no adaptador;
- a tarefa terminou `failed`;
- nenhuma ação física foi executada.

Esse teste comprovou que o fallback ocorre antes da execução física.

### Segundo teste após melhorar diagnóstico HTTP

O mesmo pedido foi repetido depois de atualizar e reiniciar o Robô.

Resultado observado no log real:

- Z.AI respondeu `HTTP 429: 1305: The service may be temporarily overloaded, please try again later`;
- o roteador tentou Gemini como fallback;
- Gemini respondeu HTTP com sucesso, porém o texto retornado não chegou como JSON válido ao parser;
- o erro registrado foi `gemini: resposta não contém JSON válido`;
- a tarefa terminou `failed`;
- novamente nenhuma ação física foi executada.

A documentação oficial do Z.AI classifica o código `1305` como rate limit; portanto o erro observado é uma indisponibilidade/limitação transitória do provedor, não falha da Policy Layer nem do executor.

## Correção vigente do Gemini

Foi inspecionado o repositório `leon337/meu_primeiro_agente`, onde o Gemini já funciona usando o SDK oficial `google-genai`, `genai.Client(...)` e `client.models.generate_content(...)`. O projeto também usa `gemini-3.6-flash` na configuração/testes locais.

Com base nessa implementação real já funcional, o adaptador Gemini do `project-memory` foi migrado de REST manual para o mesmo padrão de SDK:

- dependência `google-genai>=1.0,<2.0` adicionada ao projeto;
- `GeminiProvider` usa `genai.Client`;
- chamada por `client.models.generate_content(...)`;
- modelo padrão: `gemini-3.6-flash`;
- `GenerateContentConfig` exige `response_mime_type=application/json` e o mesmo `ACTION_SCHEMA`;
- timeout mínimo de 10,5 s e configuração de retry transitório seguem o padrão já usado no outro projeto;
- resposta `parsed` ou texto JSON ainda precisa validar como `StructuredAction`;
- erro do SDK é convertido para `ProviderGenerationError` sem copiar a chave para telemetria.

O SDK não dá acesso direto ao computador: a saída continua passando pelo mesmo `StructuredAction` → Policy Layer → executor.

O commit de testes dessa migração (`1f17fce507c9be7bd5f534e32895df9d6ec40a48`) concluiu instalação, compilação e testes com `success` no CI.

Ainda falta validar fisicamente essa versão com a API real no Linux alvo.

## Provedores e credenciais — estado atual

- **Z.AI / `glm-4.7-flash`**: conta e API key criadas; tela real de Rate Limits mostrou `concurrency limit = 1`; chave configurada localmente no `.env`; chamadas reais atualmente podem retornar `429/1305`;
- **Google Gemini / `gemini-3.6-flash`**: chave configurada localmente no `.env`; adaptador vigente usa o SDK oficial `google-genai`;
- **Cloudflare Workers AI**: token personalizado com Workers AI Read/Edit criado e guardado localmente; ainda falta `Account ID` no `.env` para ativar o adaptador;
- **SiliconFlow**: conta e API key criadas, mas permanece opcional enquanto um modelo gratuito atual e seus limites reais não forem comprovados.

As credenciais permanecem fora do Git. O usuário optou por continuar os testes com as chaves atuais.

## Próximo bloqueio real

O próximo bloqueio é revalidar o planner no Linux real com o SDK oficial do Gemini:

- executar `git pull --ff-only`;
- como foi adicionada a dependência `google-genai`, executar uma vez `pip install -e .` dentro do `.venv` do `project-memory`;
- reiniciar o Robô pelo Painel;
- repetir `Por favor abra o editor de texto para mim`;
- confirmar se Gemini produz uma `StructuredAction` válida e o editor abre quando Z.AI estiver limitado;
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
