# STATUS

## Objetivo atual

Construir um operador digital local capaz de receber objetivos em linguagem natural, usar as capacidades disponíveis ao usuário e ao sistema operacional e continuar executando até concluir o objetivo.

## Estado verificável agora

O `main` contém o MVP 0.3 com três processos separados:

- **Painel do Robô** — `127.0.0.1:8765`;
- **Central** — `127.0.0.1:8000`;
- **Robô local** — polling autenticado, planejamento, execução, verificação e telemetria.

Painel e Central continuam locais por padrão. Publicação remota ainda não foi implementada.

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
- navegação por Playwright/Chromium em testes anteriores;
- telemetria real de Painel, Central e Robô;
- planner multi-provider com fallback;
- Gemini abrindo Xed, calculadora e navegador em testes reais anteriores.

## Providers

O modo `multi` possui adaptadores para:

- **Z.AI / GLM**;
- **Google Gemini** via SDK oficial `google-genai`;
- **Cloudflare Workers AI**, ainda sem `Account ID` configurado no ambiente real.

Estado observado nos testes recentes:

- Z.AI pode retornar `429/1305`;
- Gemini retornou `429 RESOURCE_EXHAUSTED` por quota;
- tarefas simples conhecidas não devem depender de várias chamadas externas consecutivas.

## Teste físico `abrir + escrever` — PASS

Em 2026-08-09 foi repetido:

`Abra o editor de texto e escreva Olá mundo`

Resultado real após as correções:

- Xed abriu;
- o foco ficou correto;
- o texto exibido foi exatamente `Olá mundo`, incluindo o caractere `á`;
- a task terminou `succeeded`;
- o log registrou `planner=deterministic rota=local-sequence etapas=2 objetivo=concluido`;
- nenhuma chamada ao Gemini, Z.AI ou Cloudflare foi necessária para concluir essa tarefa.

Esse teste valida fisicamente a sequência local:

```text
open_app(editor)
→ verificar
→ type_text("Olá mundo")
→ verificar
→ objetivo concluído
```

Também valida o novo caminho de digitação Unicode no Linux/X11.

## Teste físico de navegador + site — FAIL

Na sequência foram testadas frases equivalentes a:

`abrir o navegador e acessar globo.com`

`Abra o navegador e acessa o site globo.com`

Resultado real:

- as tasks terminaram `failed`;
- o navegador/site não foi concluído como solicitado.

A causa foi localizada no parser determinístico: ele já reconhecia `abrir globo.com` e `abrir o navegador brave`, mas não reconhecia ainda a construção composta `abrir navegador + acessar site`.

## Correção de navegador implementada no `main` — validação física pendente

`src/context_anchor/policy.py` agora reconhece localmente construções do tipo:

```text
abrir/abra/abre navegador + acessar/acesse/acessa/visitar site
```

Exemplos cobertos:

```text
abrir o navegador e acessar globo.com
→ open_url(https://globo.com)
```

```text
Abra o navegador e acessa o site globo.com
→ open_url(https://globo.com)
```

Quando o navegador é genérico, o destino usa o executor estruturado Playwright/Chromium.

Quando um navegador específico é pedido, por exemplo:

```text
abra o navegador brave e acesse globo.com
```

o plano local preserva o navegador solicitado e abre o aplicativo com a URL como argumento:

```text
open_app("brave-browser https://globo.com")
```

Esses casos não precisam de provider externo.

## Caminhos locais vigentes

### Aplicativo simples

- alvo que parece URL/domínio → `open_url`;
- outro alvo → `open_app`.

Exemplo:

`abrir o navegador brave` → `open_app(brave-browser)`.

### Aplicativo + texto

`abrir aplicativo + escrever/digitar texto` é executado como sequência local verificada.

### Navegador + site

`abrir navegador + acessar site` é resolvido localmente para navegação estruturada ou para o navegador específico solicitado.

## Loop por IA continua existindo

O loop `ação → observação → nova decisão → ... → finish` continua vigente para pedidos que realmente exigem raciocínio, condição, ambiguidade ou replanejamento.

A otimização local não substitui o loop por IA; ela evita uso de quota quando a intenção é determinística.

## Validação automatizada

A suíte cobre agora:

- preservação de `Olá mundo` na sequência local;
- execução `open_app → type_text` sem provider;
- entrada Unicode no backend de desktop;
- `abrir o navegador brave` como aplicativo local;
- pedido educado para Brave;
- `abrir o navegador e acessar globo.com` → `open_url(https://globo.com)`;
- `Abra o navegador e acessa o site globo.com` → `open_url(https://globo.com)`;
- `abra o navegador brave e acesse globo.com` → Brave com URL como argumento.

GitHub Actions CI run `31307288547` terminou com **success** em Install, Compile e Test após a correção de navegação.

## Controles que permanecem

Continuam implementados:

- parada de emergência persistente;
- FAILSAFE físico próprio nos quatro cantos;
- verificação de foco antes de teclado quando há janela esperada observável;
- execução de processos do resolvedor com `shell=False`;
- credenciais fora de código, Git, logs e prompts;
- Painel e Central em localhost por padrão.

## Ainda não validado fisicamente após a correção mais recente

- `abrir o navegador e acessar globo.com` pelo novo caminho local;
- `abra o navegador brave e acesse globo.com` preservando Brave;
- primeiro objetivo condicional real usando o loop por IA;
- Cloudflare ativo no router real;
- percepção semântica de screenshots/árvore de acessibilidade;
- multimodalidade;
- câmera;
- publicação remota segura;
- WhatsApp, Telegram e Instagram.
