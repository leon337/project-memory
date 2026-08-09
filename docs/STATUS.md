# STATUS

## Objetivo atual

Construir um operador digital local capaz de receber objetivos em linguagem natural, usar as capacidades que o usuário e o sistema operacional permitem e continuar executando etapas até concluir o objetivo.

## Estado verificável agora

O `main` contém o MVP 0.3 com três processos separados:

- **Painel do Robô** — `127.0.0.1:8765`;
- **Central** — `127.0.0.1:8000`;
- **Robô local** — polling autenticado, planner, execução e telemetria.

Painel, Central e Robô continuam locais por padrão. Publicação remota ainda não foi implementada.

## Capacidades já validadas fisicamente

No Linux/X11 real já foram validados:

- ligar, parar e reiniciar Central e Robô pelo Painel;
- parada de emergência persistente e liberação consciente;
- FAILSAFE explícito nos cantos da tela;
- screenshot;
- movimento e clique de mouse;
- abertura de aplicativos;
- digitação e tecla Enter;
- proteção de foco entre ações de teclado;
- navegação por Playwright/Chromium;
- telemetria real de Painel, Central e Robô;
- planner multi-provider com fallback Z.AI → Gemini;
- primeira ação planejada por IA real e executada fisicamente: Gemini abriu Xed e a tarefa terminou `succeeded` com janela verificada.

## Planner multi-provider

O modo `multi` está implementado com:

- Z.AI / GLM;
- Google Gemini pelo SDK oficial `google-genai`;
- Cloudflare Workers AI preparado, mas ainda sem `Account ID` configurado no ambiente real.

O Gemini vigente usa `gemini-3.6-flash`, `response_json_schema` e `max_output_tokens=1024`.

Nos testes reais, Z.AI pode responder `HTTP 429 / 1305`; o router faz fallback antes de qualquer execução física.

## Testes físicos adicionais de 2026-08-09

Depois da primeira aceitação IA → editor, foram feitos novos testes de linguagem natural:

### Calculadora

Pedido equivalente a:

`Eu preciso fazer algumas contas, abra a calculadora para mim`

Resultado físico:

- calculadora abriu;
- tarefa `succeeded`;
- logs registraram `planner=gemini` e `rota=fast`.

### Navegador

Pedido equivalente a:

`Quero navegar na internet, abra o navegador para mim`

Resultado físico:

- Firefox abriu;
- tarefa `succeeded`;
- logs registraram `planner=gemini` e `rota=fast`.

### Photoshop — falha da política antiga

Pedido:

`Abra o Photoshop para mim`

Resultado físico antes da inversão de política:

- tarefa `failed`;
- `PermissionError: Aplicativo fora da allowlist local.`

Esse resultado ajudou a confirmar que a allowlist fixa contrariava a direção desejada do produto.

### Variação natural do editor — falha da política antiga

Pedido:

`Preciso escrever uma anotação, poderia abrir um editor de texto?`

Resultado observado antes da inversão de política:

- tarefa `failed` com `PermissionError: Aplicativo fora da allowlist local.`

### Objetivo composto — falso sucesso no nível do objetivo

Pedido:

`Abra o editor de texto e escreva Olá mundo`

Resultado físico:

- Xed abriu;
- o texto **não foi digitado**;
- mesmo assim a tarefa apareceu como `succeeded`.

A causa foi confirmada no código: `execute_command()` encerrava a tarefa depois de uma única `StructuredAction`. Portanto o sucesso da ação `open_app` estava sendo confundido com conclusão do objetivo inteiro.

### Brave — duas falhas diferentes

Testes com pedidos para abrir Brave mostraram:

1. uma frase começando exatamente por `abrir ` foi capturada pelo parser determinístico como se o restante fosse URL, produzindo navegação inválida semelhante a `%20navegador%20brave` em Chromium/Chrome for Testing;
2. uma formulação mais natural chegou ao planner de IA, mas ainda encontrou a política antiga de aplicativos.

Esses testes provaram que era necessário separar melhor **URL** de **aplicativo** e remover a autorização baseada em cadastro fixo.

## Mudança de política — implementada no código, validação física pendente

A direção vigente agora é **permissiva por padrão no perfil local confiável**.

Implementado no `main`:

- `open_app` não exige mais que o aplicativo pertença a `SUPPORTED_APP_IDS` para ser autorizado pela Policy Layer;
- URLs HTTP/HTTPS locais, privadas ou públicas não são mais bloqueadas apenas por serem locais/privadas;
- nomes de tecla imprimíveis não dependem mais de uma allowlist fechada;
- aliases conhecidos continuam existindo apenas como conveniência;
- `desktop.py` tenta resolver também executáveis/comandos que não estejam em `APP_COMMANDS`;
- argumentos são preservados com `shlex.split(...)` e execução por `subprocess.Popen(..., shell=False)`;
- Brave recebeu aliases de conveniência para `brave-browser`, `brave-browser-stable` ou `brave` quando instalados;
- caminho determinístico `abrir ...` só assume `open_url` quando o alvo realmente se parece com URL/domínio; frases como `abrir o navegador brave` passam para o planner de IA.

A tabela `APP_COMMANDS` permanece no código somente como resolvedor de aliases/candidatos conhecidos, não como fronteira de autorização.

## Loop orientado a objetivo — implementado no código, validação física pendente

Foi implementada a primeira versão do ciclo multietapa para pedidos planejados por IA:

```text
objetivo original
→ planner escolhe próxima ação
→ Policy Layer
→ executor
→ observação compacta do resultado
→ planner recebe objetivo + histórico
→ próxima ação
→ ...
→ action=finish
→ task succeeded
```

Detalhes atuais:

- `StructuredAction` ganhou a ação interna `finish`;
- o provider continua escolhendo **uma próxima ação por vez**, em vez de gerar uma lista inteira antecipadamente;
- depois de cada ação verificada, o Robô devolve ao planner um histórico compacto da etapa;
- `finish` só encerra a task depois de pelo menos uma etapa executada;
- se uma etapa retornar `verified=False`, o objetivo falha e não pode virar falso `succeeded`;
- o loop tem limite configurável `CONTEXT_ANCHOR_GOAL_MAX_STEPS`, padrão 8;
- o resultado final preserva lista de etapas e trace de providers/rotas/fallbacks;
- o caminho determinístico simples continua sendo uma execução única para preservar quota e compatibilidade.

O teste automatizado cobre explicitamente:

`open_app(editor) → type_text("Olá mundo") → finish`.

Também há testes para limite de etapas e recusa de falso sucesso quando a etapa não é verificada.

## Validação automatizada

No `main`, foram adicionados testes para:

- política local permissiva;
- `abrir o navegador brave` não ser tratado como URL pelo parser determinístico;
- aplicativo não cadastrado ser autorizado pela Policy Layer;
- resolução de executável não cadastrado;
- preservação de argumentos com `shell=False`;
- loop `open_app → type_text → finish`;
- limite de etapas;
- etapa não verificada impedir conclusão falsa.

GitHub Actions CI run `31305151754` concluiu com **success** nas etapas Install, Compile e Test.

## Estado de segurança/controle que permanece

Mesmo com a política local permissiva, continuam implementados:

- parada de emergência persistente;
- FAILSAFE físico próprio nos quatro cantos;
- verificação de foco antes de teclado quando há janela esperada observável;
- execução de processos com `shell=False` no resolvedor atual;
- credenciais fora de código, Git, logs e prompts;
- Painel e Central em localhost por padrão.

Esses itens não funcionam como allowlist de aplicativos; são mecanismos operacionais independentes.

## Próxima validação física obrigatória

A nova implementação **ainda não foi validada no computador real**.

O primeiro teste deve repetir exatamente:

`Abra o editor de texto e escreva Olá mundo`

Critério de sucesso:

1. abrir Xed/Gedit;
2. manter o foco correto;
3. digitar `Olá mundo`;
4. planner retornar `finish` depois das etapas;
5. task terminar `succeeded` somente depois da conclusão integral.

Depois deve ser repetido o teste do Brave para confirmar que ele abre como aplicativo e não como URL.

## Ainda não implementado ou não validado

- validação física do novo loop multietapa;
- validação física da política permissiva e do resolvedor genérico de aplicativos;
- percepção semântica de conteúdo de janela/screenshot;
- árvore de acessibilidade;
- multimodalidade ligada ao router;
- provider/rota/target persistidos também quando uma etapa falha antes de produzir resultado final;
- Cloudflare ativo no router real;
- quota manager completo por provider;
- câmera;
- publicação remota segura;
- WhatsApp, Telegram e Instagram.
