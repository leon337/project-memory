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

Pedido equivalente validado:

`Abra o navegador brave e acesse o site google.com`

Resultado real:

- Brave abriu;
- Google foi carregado;
- task `succeeded`;
- nenhum provider externo foi necessário.

## Teste físico `Brave + Google + pesquisar` — PASS

Foi validado no computador real um pedido equivalente a:

`Abra o navegador brave e acesse o site google.com e pesquise o São Lourenço da Mata`

Resultado real:

- Brave foi preservado;
- a pesquisa do Google foi carregada;
- task `succeeded`;
- fluxo resolvido localmente.

Outro teste também abriu a pesquisa pelo significado do nome Josiel quando a intenção foi explicitamente formulada como pesquisa.

## Baseline físico de autonomia em linguagem natural — CONCLUÍDO

Foi executada uma bateria sem corrigir cada frase durante o teste, para medir a dependência real de sintaxe específica.

### 1. Inferência de aplicativo por necessidade — FAIL

Pedido:

`Quero fazer uma anotação. Abra alguma coisa onde eu possa escrever`

Resultado:

- task `failed`;
- o sistema não conseguiu inferir de forma confiável uma capacidade de edição sem formulação explícita;
- durante essa bateria os providers externos também estavam degradados por quota/resposta inválida.

Classificação principal: **interpretação de intenção + dependência de provider**.

### 2. Resolução de nome de aplicativo — RESULTADO MISTO

Pedido:

`Abra o Visual Studio Code`

Resultado:

- **PASS**;
- VS Code abriu fisicamente;
- task `succeeded`.

Pedido equivalente:

`Abra o VS Code`

Resultado:

- **FAIL**;
- log: `FileNotFoundError: Nenhum executável instalado foi encontrado para o aplicativo/comando 'vs code'`.

Conclusão: a capacidade existe, mas a resolução de entidades/sinônimos de aplicativos ainda é inconsistente.

Classificação: **resolução de aplicativo/capacidade**.

### 3. Inferência de capacidade — FAIL

Pedido:

`Preciso fazer algumas contas.`

Resultado:

- task `failed`;
- log: `FileNotFoundError: Nenhum executável instalado foi encontrado para o aplicativo/comando 'calc'`.

A intenção de calculadora foi parcialmente inferida, mas o resolvedor escolheu um executável que não existe no ambiente Linux real.

Classificação: **resolução de aplicativo/capacidade**.

### 4. Objetivo informacional sem prescrever ferramenta — FAIL

Pedido:

`Quero saber o significado do nome Josiel`

Resultado:

- task `failed`;
- router não conseguiu gerar plano válido;
- Gemini retornou `429 RESOURCE_EXHAUSTED` durante a bateria.

Classificação: **provider/quota**, expondo também dependência excessiva de provider para um objetivo simples.

### 5. Pesquisa natural sem verbo de ferramenta — FAIL

Pedido:

`Descubra informações sobre São Lourenço da Mata`

Resultado:

- task `failed`;
- Z.AI retornou `429/1305`;
- Gemini retornou `429 RESOURCE_EXHAUSTED`.

Classificação: **provider/quota + interpretação geral de objetivo**.

### 6. Memória operacional entre tarefas — NÃO VALIDADA

O teste de referência contextual não chegou a uma validação confiável porque os objetivos anteriores que deveriam estabelecer o contexto falharam.

Continua sem existir memória operacional explícita para expressões como `agora`, `lá`, `nesse navegador`, `nesse site` e `depois` entre tasks independentes.

Classificação: **contexto entre tarefas**.

### 7. Objetivo multi-etapa com leitura de resultado — FALSO PASS

Pedido:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

O Painel marcou a task como `succeeded`, porém a observação física mostrou que:

- o navegador abriu uma pesquisa no DuckDuckGo;
- a consulta enviada ao mecanismo de busca continha praticamente o pedido inteiro, incluindo `e depois abra um editor de texto...`;
- o Robô **não leu o primeiro resultado**;
- o Robô **não abriu o editor**;
- o Robô **não escreveu o título**.

Portanto esse resultado é **FAIL no nível do objetivo**, apesar de `status=succeeded`.

Esse é o achado mais crítico do baseline: o sistema ainda pode confundir **sucesso de uma ação intermediária** com **conclusão do objetivo completo**.

Classificação: **interpretação de objetivo + percepção/observação + verificação de conclusão**.

### 8. Objetivo condicional — FAIL

Pedido equivalente a:

`Verifique se example.com está acessível. Se estiver, abra um editor e escreva "site acessível". Se não estiver, escreva "site indisponível".`

Resultado:

- task `failed`;
- não houve evidência física de observação da condição seguida da ramificação correta.

Classificação: **percepção/observação + decisão condicional + replanejamento**, com dependência de provider ainda presente.

## Conclusão do baseline

O executor físico já consegue realizar ações úteis e sequências determinísticas conhecidas. O gargalo principal agora é o **cérebro operacional**.

Não é correto continuar resolvendo autonomia por adição de frases/regex específicas.

O próximo estágio precisa transformar objetivos naturais em uma representação operacional explícita, acompanhar estado e evidências entre etapas e só marcar `succeeded` quando o objetivo completo tiver critérios de conclusão satisfeitos.

## Decisão arquitetural tomada — Goal Runtime universal

Após o baseline e duas revisões arquiteturais independentes, foi adotada a direção de um **Goal Runtime universal em ciclo fechado**.

A arquitetura alvo é:

```text
Goal Contract
→ estado operacional / blackboard
→ resolução de capacidade
→ próxima etapa
→ Policy Layer
→ executor
→ Execution Receipt
→ observação
→ evidência
→ Goal Verifier
→ replanejamento ou conclusão
```

Princípios já definidos:

- fast paths determinísticos permanecem, mas como skills/otimizações dentro do mesmo Goal Run;
- ação executada não equivale automaticamente a objetivo concluído;
- planner não possui autoridade final para emitir `succeeded`;
- somente o Goal Verifier pode fechar o objetivo quando todos os critérios obrigatórios estiverem comprovados;
- a migração será incremental, sem reescrever Painel, Central, SQLite/fila/leases, executores, Policy Layer, FAILSAFE, Emergency Stop ou providers.

## Trabalho preparatório desta sessão

A documentação vigente já foi alinhada para a nova arquitetura:

- `DECISIONS.md` contém a decisão D-022 do Goal Runtime universal;
- `ARCHITECTURE.md` descreve o pipeline alvo e separa planner, executor, percepção, evidência e verifier;
- `NEXT.md` foi reduzido à fundação leve, migração pesada do `local_agent` e evolução posterior de percepção/capacidades/contexto.

A preparação de código ainda está em andamento nesta sessão. Nenhuma refatoração pesada do fluxo real foi declarada concluída.

## Lacuna principal para autonomia real

A autonomia desejada exige que o usuário possa expressar algo como:

```text
Quero saber o significado do nome Josiel.
```

sem precisar determinar navegador, mecanismo de busca, URL ou sequência de cliques.

O sistema deve operar assim:

```text
objetivo do usuário
→ interpretar intenção e entidades
→ observar estado atual
→ escolher capacidades disponíveis
→ decompor objetivo em subobjetivos
→ planejar próxima ação
→ executar
→ coletar evidência do resultado
→ atualizar estado operacional
→ verificar se o objetivo completo foi satisfeito
→ replanejar se necessário
→ concluir somente quando houver evidência suficiente
```

## Caminhos determinísticos locais vigentes

Continuam úteis como fast path para tarefas inequívocas:

- abrir URL/domínio;
- abrir aplicativo;
- pesquisar/buscar/procurar;
- abrir aplicativo + escrever/digitar;
- abrir navegador + acessar site;
- navegador + mecanismo de busca + consulta.

Esses caminhos devem permanecer como atalhos confiáveis, não como linguagem obrigatória para o usuário.

## Loop por IA atual — em migração

O loop já implementado continua sendo:

```text
ação → observação → nova decisão → ... → finish
```

Mas o baseline mostrou que ainda falta um contrato explícito de objetivo/subobjetivos/evidências/conclusão, além de percepção suficiente para validar tarefas complexas. A decisão D-022 estabelece que esse loop deixará de ter uma semântica paralela de conclusão e será absorvido pelo Goal Runtime universal.

## Controles que permanecem

Continuam implementados:

- parada de emergência persistente;
- FAILSAFE físico próprio nos quatro cantos;
- verificação de foco antes de teclado quando há janela esperada observável;
- execução de processos com `shell=False`;
- credenciais fora de código, Git, logs e prompts;
- Painel e Central em localhost por padrão.

## Ainda não validado/implementado para autonomia completa

- fundação tipada do Goal Runtime;
- camada geral de interpretação de objetivos;
- decomposição em subobjetivos verificáveis;
- resolução geral de aplicativos instalados e sinônimos;
- persistência de contexto entre tarefas e navegadores;
- verificador de conclusão do objetivo completo integrado ao runtime real;
- primeiro objetivo condicional real usando percepção + decisão + replanejamento;
- Cloudflare ativo no router real;
- percepção semântica de DOM/árvore de acessibilidade;
- percepção visual multimodal integrada ao loop;
- câmera;
- publicação remota segura;
- WhatsApp, Telegram e Instagram.
