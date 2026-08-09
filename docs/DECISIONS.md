# DECISIONS

## D-001 — Objetivo principal

O projeto constrói um operador digital local capaz de receber um objetivo em linguagem natural e executar quantas etapas forem necessárias até concluí-lo.

O operador deve poder usar mouse, teclado, aplicativos, navegador, sites, sessões autenticadas e outras capacidades que o usuário e o sistema operacional disponibilizem.

## D-002 — Perfil local permissivo por padrão

No perfil local confiável, a ausência de uma allowlist não deve bloquear uma capacidade já disponível ao usuário e ao sistema operacional.

A direção é **permitir por padrão e bloquear por exceção**. Restrições futuras entram como denylist ou regras explícitas escolhidas pelo usuário.

Falha por ausência de implementação ou ausência do executável no sistema é diferente de bloqueio por política.

## D-003 — Aplicativos, executáveis e argumentos

Abrir aplicativos não exige cadastro manual prévio.

`APP_COMMANDS` e aliases conhecidos existem apenas como conveniência de resolução. O backend também pode tentar executar nomes/comandos não cadastrados.

O resolvedor atual separa argumentos com `shlex.split(...)` e usa `subprocess.Popen(..., shell=False)`. Caminhos e argumentos locais não são proibidos por uma allowlist de aplicativos.

Se o usuário quiser bloquear um aplicativo, executável, argumento ou classe de ação específica, isso deverá ser expresso posteriormente como regra de bloqueio.

## D-004 — Browser e URLs

`open_url` representa navegação para uma URL e usa Playwright/Chromium.

`open_app` representa abertura de um navegador/aplicativo instalado.

O parser determinístico só deve tratar `abrir ...` como URL quando o alvo se parecer de fato com URL/domínio. Frases como `abrir o navegador brave` devem ir para o planner de IA.

No perfil local, URLs HTTP/HTTPS locais, privadas e públicas são permitidas por padrão.

## D-005 — Loop orientado a objetivo

Uma ação bem-sucedida não significa automaticamente que o objetivo inteiro foi concluído.

Pedidos de IA seguem o ciclo:

```text
objetivo
→ próxima ação
→ execução
→ observação/verificação
→ nova decisão
→ ...
→ finish
```

A IA escolhe uma próxima ação por vez. Ela não precisa antecipar uma lista completa de passos.

`finish` só pode encerrar uma tarefa depois de pelo menos uma etapa executada. Uma etapa com `verified=False` impede conclusão bem-sucedida.

O loop possui limite de etapas para impedir repetição infinita; o padrão atual é 8 e pode ser configurado por `CONTEXT_ANCHOR_GOAL_MAX_STEPS`.

## D-006 — Planner determinístico permanece como caminho rápido

Comandos inequívocos já suportados continuam sendo resolvidos localmente antes de chamar uma API externa.

Isso reduz latência e uso de quota.

Pedidos naturais ou não reconhecidos seguem para o planner multi-provider.

## D-007 — Planner por IA é multi-provider

O sistema não depende de um único provider.

Conjunto inicial:

- Z.AI / GLM;
- Google Gemini;
- Cloudflare Workers AI.

O router considera tipo de tarefa, falhas recentes, cooldown, latência e limites locais de requisição.

Fallback de provider ocorre antes da ação física correspondente. Uma ação já executada não deve ser repetida automaticamente só porque uma chamada posterior de IA falhou.

## D-008 — Gemini usa o SDK oficial `google-genai`

Gemini usa `client.models.generate_content(...)`, modelo padrão `gemini-3.6-flash`, `response_json_schema=ACTION_SCHEMA` e `max_output_tokens=1024`.

Toda resposta é revalidada como `StructuredAction`.

## D-009 — StructuredAction continua tipada

A IA não controla diretamente mouse, teclado ou processos. Ela produz uma `StructuredAction`, que é convertida em `Plan` e executada pelo Robô.

Ações implementadas atualmente:

- `open_url`;
- `capture_screen`;
- `active_window`;
- `move_mouse`;
- `click_mouse`;
- `type_text`;
- `press_key`;
- `open_app`;
- `finish` interno ao loop.

Uma capacidade nova precisa de executor real; não será considerada “bloqueada” apenas porque ainda não existe no código.

## D-010 — Foco observável antes de teclado

Abrir um aplicativo ou clicar pode estabelecer uma janela esperada.

Antes de `type_text` ou `press_key`, se a janela ativa observável mudou, a entrada de teclado deve ser recusada para evitar digitação no local errado.

Essa regra acompanha identidade/foco de janela e não uma lista de aplicativos autorizados a receber teclado.

## D-011 — FAILSAFE físico independente

Além do FAILSAFE do PyAutoGUI, o Robô verifica uma zona própria de 20 pixels nos quatro cantos antes de mover mouse, clicar, digitar ou pressionar tecla.

Se o ponteiro estiver nessa zona, a entrada física é recusada antes da execução.

## D-012 — Parada de emergência independente do planner

A parada de emergência usa estado persistente e continua operando mesmo se planner, provider ou comunicação estiverem com problema.

O Robô não volta a executar até liberação consciente.

## D-013 — Credenciais separadas do raciocínio

Senhas, tokens e outras credenciais não entram em código, Git, logs ou prompts.

As chaves dos providers permanecem em configuração local.

## D-014 — Controle observável

Resultados devem ser verificáveis e correlacionáveis por tarefa.

Painel, Central e Robô mantêm telemetria real. O sistema deve distinguir sucesso de uma etapa de conclusão do objetivo inteiro.

## D-015 — Painel como centro local de operação

O Painel do Robô permanece processo separado da Central e do Robô.

Ele deve mostrar estado real, controles, diagnóstico, fila, histórico e logs, além de permitir ligar/parar/reiniciar componentes sem dependência normal de vários terminais.

## D-016 — Linux/X11 permanece primeiro alvo

O primeiro backend físico é Linux/X11 com Python 3.11+, FastAPI, SQLite, PyAutoGUI, `xdotool` quando disponível e Playwright para navegação estruturada.

## D-017 — Local e remoto são decisões separadas

Painel e Central continuam em localhost por padrão.

Permitir capacidades amplas ao operador local não significa publicar esse controle diretamente na Internet.

Acesso remoto futuro exige uma camada separada de transporte/autenticação antes de Web remoto, WhatsApp, Telegram ou Instagram entrarem em produção.

## D-018 — Documentação é memória do projeto

`docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` e `docs/NEXT.md` devem refletir o estado verificável e as decisões vigentes para que uma sessão nova possa reconstruir o projeto sem memória de chat.
