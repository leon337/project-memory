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
- navegação com navegador específico `abrir Brave + acessar site` sem provider externo;
- sequência local `Brave + Google + pesquisar` sem provider externo.

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

## Teste físico `Brave + site` — PASS

Pedido validado em forma equivalente a:

`Abra o navegador brave e acesse o site google.com`

Resultado real:

- Brave abriu;
- Google foi carregado;
- task `succeeded`;
- nenhum provider externo foi necessário.

## Teste físico `Brave + Google + pesquisar` — PASS

Após a correção do parser de pesquisa, foi validado no computador real um pedido equivalente a:

`Abra o navegador brave e acesse o site google.com e pesquise o São Lourenço da Mata`

Resultado real observado:

- Brave abriu/preservou o navegador solicitado;
- a pesquisa do Google foi carregada;
- task `succeeded`;
- o fluxo foi resolvido localmente.

Outro teste anterior também abriu a pesquisa pelo significado do nome Josiel.

Isso confirma fisicamente que uma sequência determinística de três partes pode ser concluída sem provider externo quando sua intenção já está mapeada localmente.

## Baseline de autonomia em linguagem natural — LIMITADO

Os testes físicos mais recentes também mostraram que capacidades funcionais ainda dependem demais da formulação exata do pedido.

Exemplos observados como `failed`:

- `Acesse a internet em qualquer navegador e pesquise por São Lourenço da Mata`;
- pedido em forma equivalente a `Acesse o navegador Chrome e pesquise por São Lourenço da Mata`;
- `Abrir o aplicativo Vs code`.

No caso de VS Code, o log registrou `FileNotFoundError` porque o resolvedor chegou ao backend com o alvo literal `vs code`, em vez de normalizar de forma geral para o executável instalado.

Esses FAILs não demonstram ausência das capacidades de navegador, pesquisa ou abertura de aplicativo. Eles demonstram uma lacuna de **interpretação, normalização de intenção, resolução de entidades e contexto operacional**.

Portanto o próximo avanço não deve ser adicionar um `regex` específico para cada frase que falhar.

## Lacuna principal para autonomia real

O Robô já possui executor físico e um loop orientado a objetivo, mas ainda falta uma camada geral que transforme linguagem natural variada em intenção operacional.

A autonomia desejada exige que o usuário possa expressar um objetivo como:

```text
Quero saber o significado do nome Josiel.
```

sem precisar determinar navegador, mecanismo de busca, URL ou sequência de cliques.

O sistema deve ser capaz de:

```text
objetivo do usuário
→ interpretar intenção
→ observar estado atual
→ escolher capacidades disponíveis
→ planejar próxima ação
→ executar
→ verificar resultado
→ replanejar se necessário
→ concluir quando o objetivo estiver realmente atendido
```

Para isso ainda são necessários, principalmente:

1. **interpretação geral de objetivo** — sinônimos e frases naturais não podem depender de padrões exatos;
2. **resolução de entidades/capacidades** — `VS Code`, `editor`, `navegador`, `internet`, `pesquisa` devem ser associados às capacidades reais disponíveis;
3. **memória operacional entre tarefas** — expressões como `agora`, `nesse navegador`, `nesse site`, `depois` precisam referenciar o estado anterior;
4. **percepção mais rica** — URL atual, conteúdo DOM/texto de página, janela ativa, árvore de acessibilidade e posteriormente percepção visual;
5. **replanejamento por resultado** — se uma ação falha ou produz estado diferente, escolher outra estratégia em vez de depender de nova formulação humana.

## Caminhos determinísticos locais vigentes

Continuam úteis como fast path para tarefas inequívocas:

- abrir URL/domínio;
- abrir aplicativo;
- pesquisar/buscar/procurar;
- abrir aplicativo + escrever/digitar;
- abrir navegador + acessar site;
- navegador + mecanismo de busca + consulta.

Esses caminhos devem funcionar como atalhos confiáveis, não como linguagem obrigatória para o usuário.

## Loop por IA

O loop já implementado continua sendo:

```text
ação → observação → nova decisão → ... → finish
```

Ele é necessário para condição, interpretação de conteúdo, ambiguidade e replanejamento.

O caminho local apenas evita chamadas de IA quando a próxima ação já é determinística.

## Limitações atuais do loop autônomo

Mesmo com o loop implementado, autonomia sem formulação rígida ainda está limitada porque:

- providers externos estão instáveis por quota/resposta inválida no ambiente real;
- Cloudflare ainda não está ativo no router real;
- observação semântica de páginas e desktop ainda é limitada;
- não existe memória operacional explícita entre tarefas independentes;
- resolução de nomes de aplicativos ainda não é geral o suficiente.

## Validação automatizada

A suíte cobre, entre outros casos:

- `Abra o editor de texto e escreva Olá mundo`;
- Unicode no backend de desktop;
- `abrir o navegador brave`;
- `abrir o navegador e acessar globo.com`;
- `Abra o navegador e acessa o site globo.com`;
- `abra o navegador brave e acesse globo.com`;
- `agora pesquise sobre inteligencia artificial`;
- `Abra o navegador brave e acesse o site google.com e pesquise o significado do nome Josiel`;
- `Abra o navegador e acesse google.com e pesquise inteligência artificial`.

GitHub Actions CI run `31307745802` terminou com **success** após a correção de pesquisa.

## Controles que permanecem

Continuam implementados:

- parada de emergência persistente;
- FAILSAFE físico próprio nos quatro cantos;
- verificação de foco antes de teclado quando há janela esperada observável;
- execução de processos com `shell=False`;
- credenciais fora de código, Git, logs e prompts;
- Painel e Central em localhost por padrão.

## Ainda não validado/implementado para autonomia completa

- interpretação geral de linguagem natural independente de frases pré-cadastradas;
- resolução geral de aplicativos instalados e sinônimos;
- persistência de contexto entre tarefas e navegadores;
- primeiro objetivo condicional real usando percepção + decisão + replanejamento;
- Cloudflare ativo no router real;
- percepção semântica de DOM/árvore de acessibilidade;
- percepção visual multimodal integrada ao loop;
- câmera;
- publicação remota segura;
- WhatsApp, Telegram e Instagram.
