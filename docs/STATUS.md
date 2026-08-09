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
- validação final obrigatória com `StructuredAction`;
- normalização segura de erros sem registrar a chave.

O teste automatizado agora também confirma que `response_schema` fica vazio e que `response_json_schema` preserva `additionalProperties=False`.

O commit de teste dessa correção é `6efd18d55454749d75833db00948b8728115e146`; as etapas Install, Compile e Test do CI passaram com `success` no run `31300271373`.

Ainda falta a revalidação física dessa correção no Linux real.

## Provedores e credenciais — estado atual

- **Z.AI / `glm-4.7-flash`**: conta e API key configuradas localmente; tela real de Rate Limits mostrou `concurrency limit = 1`; chamadas reais podem retornar `429/1305`;
- **Google Gemini / `gemini-3.6-flash`**: chave configurada localmente; adaptador usa SDK oficial e `response_json_schema`;
- **Cloudflare Workers AI**: token personalizado Workers AI Read/Edit criado e guardado localmente; ainda falta `Account ID` no `.env` para ativar o adaptador;
- **SiliconFlow**: conta e API key criadas, mas permanece opcional enquanto um modelo gratuito atual e seus limites reais não forem comprovados.

As credenciais permanecem fora do Git. O usuário optou por continuar os testes com as chaves atuais.

## Próximo bloqueio real

Revalidar fisicamente a correção `response_json_schema`:

1. `git pull --ff-only`;
2. reiniciar o Robô pelo Painel;
3. repetir `Por favor abra o editor de texto para mim`;
4. confirmar se Gemini gera `open_app → editor` e o Xed abre quando Z.AI estiver limitado;
5. verificar nos logs o provedor usado e o fallback.

Depois disso, obter/configurar o `Cloudflare Account ID` e ativar o terceiro provedor.

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
- WhatsApp, Telegram e Instagram;
- seletor claro/escuro e preferências visuais persistentes.
