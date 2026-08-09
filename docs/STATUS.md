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
- digitação Unicode e tecla Enter;
- proteção de foco entre ações de teclado;
- telemetria real de Painel, Central e Robô;
- planner multi-provider com fallback;
- sequência local `abrir editor + escrever` sem provider externo;
- navegação genérica `abrir navegador + acessar site` sem provider externo;
- navegação com navegador específico `abrir Brave + acessar site` sem provider externo.

## Providers

O modo `multi` possui adaptadores para:

- **Z.AI / GLM**;
- **Google Gemini** via SDK oficial `google-genai`;
- **Cloudflare Workers AI**, ainda sem `Account ID` configurado no ambiente real.

Estado observado nos testes recentes:

- Z.AI pode retornar `429/1305` ou resposta sem JSON válido;
- Gemini retornou `429 RESOURCE_EXHAUSTED` por quota;
- tarefas determinísticas conhecidas não devem depender desses providers.

## Teste físico `abrir + escrever` — PASS

Pedido validado:

`Abra o editor de texto e escreva Olá mundo`

Resultado real:

- Xed abriu;
- o foco ficou correto;
- `Olá mundo` apareceu exatamente, incluindo `á`;
- task `succeeded`;
- log: `planner=deterministic rota=local-sequence etapas=2 objetivo=concluido`;
- nenhum provider externo foi necessário.

Esse teste valida fisicamente a digitação Unicode e a sequência:

```text
open_app(editor)
→ verificar
→ type_text("Olá mundo")
→ verificar
→ objetivo concluído
```

## Teste físico `navegador + site` — PASS

Pedido validado:

`Abra o navegador e acesse o site globo.com`

Resultado real:

- o navegador estruturado abriu;
- `globo.com` foi carregado corretamente;
- task `succeeded`;
- log registrou `planner=deterministic rota=deterministic`;
- nenhum provider externo foi necessário.

Isso confirma fisicamente a correção do parser para `abrir navegador + acessar site`.

## Teste físico `Brave + site` — PASS

Também foi validado um pedido equivalente a:

`Abra o navegador brave e acesse o site google.com`

Resultado real:

- o navegador solicitado abriu;
- o destino foi acessado;
- task `succeeded`.

O caminho local preserva o navegador explicitamente solicitado e passa a URL como argumento ao processo.

## Testes físicos de pesquisa — FAIL antes da correção mais recente

### Brave + Google + pesquisar

Foi testado um pedido equivalente a:

`Abra o navegador brave e acesse o site google.com e pesquise o significado do nome Josiel`

Resultado: `failed`.

A construção tinha três partes — navegador específico, site e consulta — e ainda não existia no parser determinístico.

### Pesquisa isolada

Também foi testado:

`agora pesquise sobre inteligencia artificial`

Resultado: `failed`.

Como `pesquise` e a forma com prefixo `agora` ainda não estavam no parser local, a tarefa caiu no router externo. O log mostrou Z.AI sem plano JSON válido e Gemini com `429 RESOURCE_EXHAUSTED`.

## Correção de pesquisa implementada no `main` — validação física pendente

`src/context_anchor/policy.py` agora resolve localmente pesquisas inequívocas.

### Pesquisa simples

Variações como:

```text
pesquise inteligência artificial
agora pesquise sobre inteligência artificial
busque FastAPI
procure agentes de IA
```

viram uma URL de pesquisa em DuckDuckGo e não usam provider externo.

### Navegador + mecanismo de busca + consulta

Para mecanismos conhecidos — atualmente Google, DuckDuckGo e Bing — o parser monta diretamente a URL da pesquisa.

Exemplo com navegador específico:

```text
Abra o navegador brave e acesse o site google.com e pesquise o significado do nome Josiel
→ open_app("brave-browser https://www.google.com/search?q=o+significado+do+nome+Josiel")
```

Exemplo com navegador genérico:

```text
Abra o navegador e acesse google.com e pesquise inteligência artificial
→ open_url("https://www.google.com/search?q=intelig%C3%AAncia+artificial")
```

Nenhuma dessas formas precisa de Gemini, Z.AI ou Cloudflare.

## Limite conhecido de contexto entre tarefas

Um pedido isolado como:

`agora pesquise ...`

é atualmente interpretado como uma nova pesquisa web determinística e usa `open_url` no navegador estruturado.

Ele ainda não promete reutilizar um navegador externo específico, como Brave, que tenha sido aberto em uma tarefa anterior. Persistência explícita de contexto entre tarefas/navegadores ainda precisa ser implementada se esse for o comportamento desejado.

## Loop por IA continua existindo

O loop:

```text
ação → observação → nova decisão → ... → finish
```

continua vigente para pedidos que exigem condição, interpretação de conteúdo, ambiguidade ou replanejamento.

O caminho local apenas evita chamadas de IA quando a intenção já é determinística.

## Validação automatizada

A suíte cobre agora, entre outros casos:

- `Abra o editor de texto e escreva Olá mundo`;
- Unicode no backend de desktop;
- `abrir o navegador brave`;
- `abrir o navegador e acessar globo.com`;
- `Abra o navegador e acessa o site globo.com`;
- `abra o navegador brave e acesse globo.com`;
- `agora pesquise sobre inteligencia artificial`;
- `Abra o navegador brave e acesse o site google.com e pesquise o significado do nome Josiel`;
- `Abra o navegador e acesse google.com e pesquise inteligência artificial`.

GitHub Actions CI run `31307745802` terminou com **success** em Install, Compile e Test após a correção de pesquisa.

## Controles que permanecem

Continuam implementados:

- parada de emergência persistente;
- FAILSAFE físico próprio nos quatro cantos;
- verificação de foco antes de teclado quando há janela esperada observável;
- execução de processos com `shell=False`;
- credenciais fora de código, Git, logs e prompts;
- Painel e Central em localhost por padrão.

## Ainda não validado fisicamente após a correção mais recente

- `Brave + Google + pesquisar` pelo novo caminho local;
- pesquisa isolada com `pesquise/agora pesquise` sem provider;
- persistência de contexto entre tarefas e navegadores externos;
- primeiro objetivo condicional real usando o loop por IA;
- Cloudflare ativo no router real;
- percepção semântica de screenshots/árvore de acessibilidade;
- multimodalidade;
- câmera;
- publicação remota segura;
- WhatsApp, Telegram e Instagram.
