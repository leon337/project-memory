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
- ciclo **Parar Robô → Desligado → Ligar Robô → Ligado**;
- parada de emergência em dois ciclos reais, com bloqueio persistente e liberação consciente;
- FAILSAFE explícito em dois cantos da tela, gerando `DesktopFailsafeTriggered` antes da entrada física;
- screenshot, mouse, clique, Xed, digitação e tecla Enter;
- proteção de foco para sequências abrir aplicativo → digitar;
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
- `local_agent.py` constrói dinamicamente o roteador usando somente provedores configurados no `.env`;
- comandos que o planner determinístico já entende continuam sendo resolvidos localmente antes da IA, sem consumir quota externa;
- pedidos simples priorizam Cloudflare → Z.AI → Gemini quando disponíveis;
- pedidos com marcadores de análise/condição priorizam Z.AI → Gemini → Cloudflare;
- falha de um provedor pode acionar outro antes da execução física;
- toda saída continua validada como `StructuredAction` e depois passa pela Policy Layer.

## Testes reais do planner multi-provider

Em 2026-08-09 foi ativado `CONTEXT_ANCHOR_PLANNER_MODE=multi` no Linux real com provedores **Z.AI + Gemini** configurados localmente.

Pedido usado nos testes:

`Por favor abra o editor de texto para mim`

### Teste 1

- Robô iniciou em `planner=multi` com `providers=zai,gemini`;
- Z.AI respondeu `HTTP 429`;
- o roteador tentou Gemini;
- Gemini respondeu `HTTP 400` com o formato REST então usado;
- tarefa terminou `failed`;
- nenhuma ação física foi executada.

Esse teste comprovou que o fallback acontece antes da execução física.

### Teste 2

Após melhorar o diagnóstico HTTP:

- Z.AI respondeu `HTTP 429: 1305: The service may be temporarily overloaded, please try again later`;
- Gemini respondeu HTTP com sucesso, porém o texto retornado não chegou como JSON válido;
- erro `gemini: resposta não contém JSON válido`;
- tarefa `failed`;
- nenhuma ação física executada.

O código `1305` do Z.AI é tratado como limitação/indisponibilidade transitória.

### Migração para o SDK oficial do Gemini

Foi inspecionado o repositório `leon337/meu_primeiro_agente`, onde o Gemini já funciona via:

- `google-genai`;
- `genai.Client(...)`;
- `client.models.generate_content(...)`;
- modelo `gemini-3.6-flash`.

O `project-memory` foi migrado para o mesmo padrão. A dependência `google-genai>=1.0,<2.0` foi adicionada, o modelo padrão passou a `gemini-3.6-flash` e os testes automatizados da migração passaram no CI.

### Teste 3 — SDK oficial no Linux real

O usuário atualizou a cópia local, instalou a nova dependência e repetiu o pedido real.

Resultado observado no Painel:

- Robô iniciou em `planner=multi` com `providers=zai,gemini`;
- Z.AI continuou indisponível/limitado e o roteador fez fallback;
- Gemini foi chamado pelo SDK oficial;
- Gemini devolveu `400 INVALID_ARGUMENT`;
- a mensagem do servidor apontou `Unknown name "additional_properties" at 'generation_config.response_schema'`;
- a tarefa terminou `failed`;
- nenhuma ação física foi executada.

O problema foi localizado no adaptador: `ACTION_SCHEMA`, que é JSON Schema padrão e contém `additionalProperties`, estava sendo passado por `response_schema`. Segundo a documentação do SDK, JSON Schema padrão deve ser enviado por `response_json_schema`.

## Correção vigente do Gemini

O `GeminiProvider` agora usa:

- SDK oficial `google-genai`;
- `client.models.generate_content(...)`;
- modelo padrão `gemini-3.6-flash`;
- `response_mime_type="application/json"`;
- `response_json_schema=ACTION_SCHEMA`;
- `max_output_tokens=1024` para acomodar os tokens de pensamento do modelo antes do JSON curto;
- validação final obrigatória com `StructuredAction`;
- normalização segura de erros sem registrar a chave.

O teste automatizado agora também confirma que `response_schema` fica vazio e que `response_json_schema` preserva `additionalProperties=False`.

O commit de teste dessa correção é `6efd18d55454749d75833db00948b8728115e146`; as etapas Install, Compile e Test do CI passaram com `success` no run `31300271373`.

### Teste 4 — ação estruturada chegou à Policy Layer

Os logs locais e o SQLite registram um teste físico posterior, também em 2026-08-09, com o pedido:

`Por favor abra o editor de texto para mim`

Resultado verificável da tarefa `86e814f9-3870-4573-9ba4-19942beddb95`:

- o pedido não pertence ao vocabulário do planner determinístico;
- ao menos um dos provedores externos configurados gerou uma `StructuredAction` válida com ação `open_app`, pois a execução chegou ao ramo específico de aplicativos da Policy Layer;
- a Policy Layer recusou o plano com `PermissionError: Aplicativo fora da allowlist local.`;
- `executor.execute()` não foi chamado e nenhuma ação física ocorreu;
- a tarefa terminou `failed` na primeira tentativa;
- o provider e o `target` exatos não foram persistidos nessa falha, porque os metadados do planner só são anexados ao resultado depois da Policy Layer e da execução.

Portanto, esse teste comprova participação de IA real e avanço além dos erros anteriores de HTTP/schema, mas não permite atribuir o plano especificamente a Z.AI ou Gemini e não satisfaz o teste de aceitação físico.

### Correção local da fronteira `open_app`

A investigação do `HEAD a127e9f` e os testes físicos posteriores mostraram que:

- `editor` já apontava somente para executáveis fixos permitidos, `xed` ou `gedit`;
- a tabela de aliases reconhecia `text editor`, mas não `editor de texto`, `text_editor`, `xed`, `gedit` ou o target real `notepad` devolvido pelo Gemini;
- `plan_from_structured()` preservava o texto não-canônico devolvido pela IA até a Policy Layer.

A correção consolidada:

- normaliza esses aliases seguros, inclusive `notepad`, para o ID canônico `editor` quando uma `StructuredAction` vira `Plan`;
- mantém caminhos, argumentos, `bash` e qualquer alvo desconhecido fora da allowlist;
- não altera StructuredAction, Policy Layer, feature gate, FAILSAFE, parada de emergência ou `shell=False`.

Validação automatizada desta correção:

- RED inicial: cinco aliases seguros falharam antes da implementação pelo motivo esperado;
- RED físico adicional: `notepad` permaneceu não-canônico até ser incluído explicitamente na tabela fechada;
- GREEN focal: `10 passed`, incluindo `notepad.exe`, caminhos, argumentos e `bash` ainda bloqueados;
- RED Gemini: o teste comprovou que o limite antigo de 160 tokens era inferior ao mínimo definido para a resposta;
- suíte completa atual: `82 passed`, com uma advertência preexistente de depreciação do TestClient;
- compilação e `git diff --check`: sucesso.

### Teste 5 — target real `notepad`

Depois de iniciar Painel, Central e Robô e reiniciar o Robô para carregar o working tree, a tarefa `99619231-fa42-42ff-a8b4-9aa2b0eae28a` repetiu o pedido exato e terminou `failed` na Policy Layer com aplicativo fora da allowlist.

Como falhas de política ainda não preservam provider/target, foi executada somente a etapa de planejamento em processo isolado, sem executor físico. Resultado:

- Z.AI falhou e o router fez fallback;
- Gemini gerou `{"action":"open_app","target":"notepad"}`;
- `notepad` não era um alias local e reproduzia exatamente a recusa;
- a tabela fechada passou a mapear `notepad → editor`, sem aceitar `notepad.exe`, caminho ou argumentos.

### Teste 6 — truncamento do Gemini

Após a correção do alias, a tarefa `07399df6-c668-4c2a-bfb8-49e64746cfa5` terminou `failed` antes da Policy Layer:

- Z.AI respondeu `HTTP 429 / 1305`;
- Gemini terminou com resposta não-JSON.

Uma chamada isolada com a mesma configuração mostrou texto parcial `Here is the` e `FinishReason.MAX_TOKENS`. O limite antigo de 160 tokens era consumido pelo pensamento do modelo antes de o JSON terminar. `thinking_budget=0` foi testado e recusado pelo modelo com `400 INVALID_ARGUMENT`, portanto não foi adotado.

Com `max_output_tokens=1024`, a mesma chamada retornou JSON completo, `FinishReason.STOP`, 104 tokens de pensamento e 11 tokens de resposta. O adaptador foi corrigido somente nesse limite; schema, temperatura e validação permaneceram iguais.

### Teste 7 — aceitação física concluída

Em 2026-08-09, a tarefa `20aafaf2-4721-4349-9f78-05076f81ede6` executou exatamente:

`Por favor abra o editor de texto para mim`

Resultado persistido e verificado:

- `planner_provider=gemini`;
- `planner_route=fast`;
- `planner_fallbacks=[zai]`;
- `action=open_app` e `app=editor`;
- Policy Layer: `Aplicativo permitido pela allowlist local.`;
- executável fixo `/usr/bin/xed`, PID `207332`;
- nova janela `Unsaved Document 1`, id `69206821`;
- `window_changed=true` e `verified=true`;
- tarefa finalizada `succeeded` na primeira tentativa, sem erro.

O processo `/usr/bin/xed` e a janela foram conferidos independentemente após a tarefa. Os logs do Painel, Central e Robô registram, respectivamente, criação, entrega, execução por Gemini/rota fast, envio do resultado e estado final `succeeded`.

### Revisão cirúrgica do guard de teclado

Durante a consolidação, o `main` remoto continha o commit `d5cb7dda06cb4f37ad21b39368e83ca168c3a861`, que adicionava uma autorização de teclado exclusiva para janelas abertas como `editor`. Essa restrição não derivava de D-015, D-022 ou D-025 e contrariava o contrato anterior em que um clique observável confirma o novo foco.

Uma worktree isolada no próprio `d5cb7dda` reproduziu a regressão antes da correção: `tests/test_desktop_focus.py` terminou com `5 failed, 1 passed`, incluindo os dois novos casos que exercitam clique → digitação e aplicativo permitido não-editor → teclado.

A revisão preservou:

- aliases seguros de editor, inclusive `editor de texto`, `text editor`, `text_editor`, `xed`, `gedit` e `notepad`;
- allowlist fixa de `open_app`, `shell=False`, Policy Layer e feature gate;
- espera de prontidão, janela esperada e recusa quando o foco muda;
- FAILSAFE explícito e parada de emergência.

Foram removidos `KEYBOARD_INPUT_APP_IDS`, os estados `_keyboard_authorized_*`, o gate de janela “segura” exclusiva do editor, a limitação que impedia clique de confirmar novo foco e o campo `keyboard_authorized` do resultado de `open_app`. A exigência incidental de `xdotool` introduzida no mesmo guard também foi retirada, restaurando o fallback anterior; a observação por `xdotool` continua sendo usada quando disponível.

## Provedores e credenciais — estado atual

- **Z.AI / `glm-4.7-flash`**: conta e API key configuradas localmente; tela real de Rate Limits mostrou `concurrency limit = 1`; chamadas reais podem retornar `429/1305`;
- **Google Gemini / `gemini-3.6-flash`**: chave configurada localmente; adaptador usa SDK oficial, `response_json_schema` e limite de output 1024 validado em chamada e execução reais;
- **Cloudflare Workers AI**: token personalizado Workers AI Read/Edit criado e guardado localmente; ainda falta `Account ID` no `.env` para ativar o adaptador;
- **SiliconFlow**: conta e API key criadas, mas permanece opcional enquanto um modelo gratuito atual e seus limites reais não forem comprovados.

As credenciais permanecem fora do Git. O usuário optou por continuar os testes com as chaves atuais.

## Marco físico atual

O objetivo desta sessão foi concluído fisicamente. Existe evidência do fluxo completo:

```text
pedido natural
→ planner multi
→ fallback Z.AI para Gemini
→ StructuredAction open_app
→ target canônico editor
→ Policy Layer aprova
→ /usr/bin/xed abre
→ janela real verificada
→ tarefa succeeded
→ logs correlacionados por task id
```

## Ainda não implementado ou não validado

- persistência de provider, rota, fallback, ação e target canônico também em falhas de política;
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
- WhatsApp, Telegram e Instagram;
- seletor claro/escuro e preferências visuais persistentes.
