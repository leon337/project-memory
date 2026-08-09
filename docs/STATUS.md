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
- digitação ASCII e tecla Enter;
- proteção de foco entre ações de teclado;
- navegação por Playwright/Chromium;
- telemetria real de Painel, Central e Robô;
- planner multi-provider com fallback;
- Gemini abrindo Xed, calculadora e navegador em testes reais anteriores.

## Providers

O modo `multi` possui adaptadores para:

- **Z.AI / GLM**;
- **Google Gemini** via SDK oficial `google-genai`;
- **Cloudflare Workers AI**, ainda sem `Account ID` configurado no ambiente real.

Estado observado nos testes mais recentes:

- Z.AI pode retornar `429/1305`;
- Gemini retornou `429 RESOURCE_EXHAUSTED` por quota;
- por isso uma tarefa simples não pode depender de várias chamadas externas consecutivas para funcionar.

## Teste físico do primeiro loop orientado a objetivo — FAIL

Em 2026-08-09 foi repetido:

`Abra o editor de texto e escreva Olá mundo`

Resultado real:

- Xed abriu;
- o Robô tentou a etapa de digitação;
- o texto exibido ficou incorreto (`ol mundo` em vez de `Olá mundo`);
- depois da ação física, o loop tentou consultar novamente o provider;
- Gemini respondeu `429 RESOURCE_EXHAUSTED`;
- a task terminou `failed`.

Nova tentativa sem acento também falhou, mas dessa vez antes de abrir o editor, porque o router não conseguiu obter um plano válido dos providers disponíveis.

Portanto o teste foi classificado como **FAIL**.

## Causas confirmadas

### 1. Unicode na digitação

`type_text()` usava somente `pyautogui.write(...)`. No Linux/X11 real esse caminho não preservou corretamente o caractere `á`.

### 2. Excesso de chamadas de IA para tarefa simples

O primeiro loop consultava a IA depois de cada etapa física e também para obter `finish`.

Para uma tarefa simples como abrir editor + digitar texto, isso criava dependência desnecessária de várias chamadas consecutivas e tornava a task vulnerável a rate limit/quota depois de já ter executado parte do objetivo.

## Correções implementadas no `main` — validação física pendente

### Digitação Unicode

`src/context_anchor/desktop.py` agora:

- continua usando `pyautogui.write(...)` para trechos ASCII;
- para caracteres não ASCII usa entrada Unicode do Linux (`Ctrl+Shift+U` + código hexadecimal + Enter);
- preserva o foco esperado e o FAILSAFE antes da digitação;
- registra `input_method` no resultado sem registrar o conteúdo digitado.

### Sequência local conhecida

`src/context_anchor/policy.py` ganhou `plan_local_sequence(...)` para o primeiro padrão composto inequívoco:

```text
abrir aplicativo + escrever/digitar texto
```

Exemplo:

`Abra o editor de texto e escreva Olá mundo`

vira localmente:

```text
open_app(editor)
→ verificar
→ type_text("Olá mundo")
→ verificar
→ objetivo concluído
```

Essa sequência não chama Gemini, Z.AI ou Cloudflare.

`src/context_anchor/local_agent.py` executa cada etapa da sequência local, registra observações e só retorna `goal_completed=true` se nenhuma etapa retornar `verified=False`.

### Abertura de aplicativos sem IA quando inequívoca

O caminho determinístico agora trata `abrir/abra/abre ...` assim:

- se o alvo parece URL/domínio → `open_url`;
- caso contrário → `open_app`.

Assim, `abrir o navegador brave` é resolvido localmente para `brave-browser` e não precisa consumir quota de IA.

Pedidos com sufixos como `para mim` e `por favor` também são normalizados.

## Loop por IA continua existindo

O loop `ação → observação → nova decisão → ... → finish` continua vigente para pedidos que realmente exigem raciocínio, condição, ambiguidade ou replanejamento.

A otimização local não substitui o loop por IA; ela evita usar IA repetidamente quando a sequência é determinística e já conhecida.

## Validação automatizada

Foram adicionados testes para:

- preservar exatamente `Olá mundo` no planejamento local;
- executar `open_app → type_text` sem qualquer chamada ao provider;
- entrada Unicode no backend de desktop;
- `abrir o navegador brave` ser resolvido localmente como aplicativo;
- formulação `abra o navegador brave para mim por favor`;
- manter o loop por IA para objetivos que não pertencem ao caminho local conhecido.

GitHub Actions CI run `31306326869` terminou com **success** em Install, Compile e Test.

## Controles que permanecem

Continuam implementados:

- parada de emergência persistente;
- FAILSAFE físico próprio nos quatro cantos;
- verificação de foco antes de teclado quando há janela esperada observável;
- execução de processos do resolvedor com `shell=False`;
- credenciais fora de código, Git, logs e prompts;
- Painel e Central em localhost por padrão.

## Ainda não validado fisicamente após as últimas correções

- sequência local `open_app(editor) → type_text("Olá mundo")`;
- entrada Unicode real com `á`;
- Brave aberto pelo caminho determinístico local;
- primeiro objetivo condicional real usando o loop por IA;
- Cloudflare ativo no router real;
- percepção semântica de screenshots/árvore de acessibilidade;
- multimodalidade;
- câmera;
- publicação remota segura;
- WhatsApp, Telegram e Instagram.
