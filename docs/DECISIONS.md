# DECISIONS

## D-001 — Objetivo principal

O projeto constrói um operador digital local capaz de receber um objetivo em linguagem natural e executar quantas etapas forem necessárias até concluí-lo.

O operador deve poder usar mouse, teclado, aplicativos, navegador, sites, sessões autenticadas e outras capacidades que o usuário e o sistema operacional disponibilizem.

## D-002 — Perfil local permissivo por padrão

No perfil local confiável, a ausência de uma allowlist não deve bloquear uma capacidade já disponível ao usuário e ao sistema operacional.

A direção é **permitir por padrão e bloquear por exceção**. Restrições futuras entram como denylist ou regras explícitas.

Falha por ausência de implementação ou ausência do executável é diferente de bloqueio por política.

## D-003 — Aplicativos, executáveis e argumentos

Abrir aplicativos não exige cadastro manual prévio.

`APP_COMMANDS` e aliases conhecidos existem como conveniência de resolução. O backend também pode tentar nomes/comandos não cadastrados.

O resolvedor separa argumentos com `shlex.split(...)` e usa `subprocess.Popen(..., shell=False)`.

## D-004 — URL e aplicativo são resolvidos localmente quando inequívocos

`open_url` representa navegação para uma URL e usa Playwright/Chromium.

`open_app` representa abertura de aplicativo/processo instalado.

Para comandos `abrir/abra/abre ...`, o parser local usa:

- alvo com formato de URL/domínio → `open_url`;
- outro alvo → `open_app`.

Assim, `abrir o navegador brave` não precisa consultar IA e deve resolver localmente para um aplicativo.

## D-005 — Loop orientado a objetivo por IA

Uma ação bem-sucedida não significa automaticamente que o objetivo inteiro foi concluído.

Pedidos que realmente precisam de IA seguem:

```text
objetivo
→ próxima ação
→ execução
→ observação/verificação
→ nova decisão
→ ...
→ finish
```

`finish` só pode encerrar uma tarefa depois de pelo menos uma etapa executada. Uma etapa com `verified=False` impede conclusão bem-sucedida.

O loop possui limite configurável; o padrão atual é 8 etapas físicas.

## D-006 — Planner determinístico é caminho rápido e pode executar sequências conhecidas

Comandos inequívocos são resolvidos localmente antes de qualquer API externa.

Além de comandos simples, sequências compostas realmente determinísticas podem ser reconhecidas e executadas localmente, com verificação entre as etapas.

Primeiro padrão composto implementado:

```text
abrir aplicativo + escrever/digitar texto
```

Essa decisão reduz latência e consumo de quota sem remover o loop por IA para objetivos condicionais, ambíguos ou dependentes de observação.

## D-007 — Planner por IA é multi-provider

O sistema não depende de um único provider.

Conjunto inicial:

- Z.AI / GLM;
- Google Gemini;
- Cloudflare Workers AI.

O router considera tipo de tarefa, falhas recentes, cooldown, latência e limites locais de requisição.

Fallback ocorre antes da ação física correspondente. Uma ação já executada não deve ser repetida automaticamente só porque uma chamada posterior de IA falhou.

## D-008 — Gemini usa o SDK oficial `google-genai`

Gemini usa `client.models.generate_content(...)`, modelo padrão `gemini-3.6-flash`, `response_json_schema=ACTION_SCHEMA` e `max_output_tokens=1024`.

Toda resposta é revalidada como `StructuredAction`.

## D-009 — StructuredAction continua tipada

A IA não controla diretamente mouse, teclado ou processos. Ela produz uma `StructuredAction`, convertida em `Plan` e executada pelo Robô.

Ações implementadas atualmente:

- `open_url`;
- `capture_screen`;
- `active_window`;
- `move_mouse`;
- `click_mouse`;
- `type_text`;
- `press_key`;
- `open_app`;
- `finish` interno ao loop por IA.

Uma capacidade nova precisa de executor real.

## D-010 — Foco observável antes de teclado

Abrir um aplicativo ou clicar pode estabelecer uma janela esperada.

Antes de `type_text` ou `press_key`, se a janela ativa observável mudou, a entrada de teclado é recusada para evitar digitar no lugar errado.

Essa regra acompanha identidade/foco de janela e não uma lista de aplicativos autorizados.

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

Painel, Central e Robô mantêm telemetria real. O sistema distingue sucesso de uma etapa de conclusão do objetivo inteiro.

## D-015 — Painel como centro local de operação

O Painel do Robô permanece processo separado da Central e do Robô.

Ele deve mostrar estado real, controles, diagnóstico, fila, histórico e logs, além de permitir ligar/parar/reiniciar componentes sem dependência normal de vários terminais.

## D-016 — Linux/X11 permanece primeiro alvo

O primeiro backend físico é Linux/X11 com Python 3.11+, FastAPI, SQLite, PyAutoGUI, `xdotool` quando disponível e Playwright para navegação estruturada.

## D-017 — Local e remoto são decisões separadas

Painel e Central continuam em localhost por padrão.

Permitir capacidades amplas ao operador local não significa publicar esse controle diretamente na Internet.

Acesso remoto futuro exige uma camada separada de transporte/autenticação.

## D-018 — Documentação é memória do projeto

`docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` e `docs/NEXT.md` devem refletir o estado verificável e as decisões vigentes para que uma sessão nova possa reconstruir o projeto sem memória de chat.

## D-019 — Quota de IA é recurso a preservar

Uma tarefa não deve consumir chamadas de IA quando a próxima sequência de ações já é determinística e verificável localmente.

IA é reservada para interpretação, decisão, condição, ambiguidade, observação semântica ou replanejamento real.

O teste físico que abriu o editor e depois falhou por `429 RESOURCE_EXHAUSTED` confirmou a necessidade desta regra.

## D-020 — Digitação Unicode precisa de caminho próprio no Linux

`pyautogui.write(...)` permanece para trechos ASCII.

Caracteres não ASCII usam entrada Unicode do Linux (`Ctrl+Shift+U` + código hexadecimal + Enter), preservando foco e FAILSAFE.

Essa decisão existe porque o teste físico de `Olá mundo` perdeu o caractere `á` usando apenas `pyautogui.write(...)`.

## D-021 — `succeeded` significa objetivo completo comprovado

O status final `succeeded` é reservado para o **objetivo completo**, não para uma ação intermediária executada com sucesso.

Cada task complexa deve manter uma representação explícita de:

- objetivo original;
- subobjetivos necessários;
- evidências coletadas após cada ação;
- critérios de conclusão.

Um fast path determinístico não pode descartar silenciosamente partes de um pedido composto.

O teste físico

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

foi marcado como `succeeded`, mas na prática apenas abriu uma pesquisa contendo quase a frase inteira; não leu o primeiro resultado, não abriu o editor e não escreveu o título. Esse resultado é tratado como **FAIL de objetivo** e motivou esta decisão.

A arquitetura implementada decompõe o objetivo, acompanha subobjetivos e só conclui quando há evidência suficiente de que todos os critérios relevantes foram atendidos.

## D-022 — Goal Runtime universal em ciclo fechado

Todo pedido deve possuir uma única semântica de conclusão, independentemente de ser resolvido por fast path determinístico ou por IA.

A unidade de sucesso deixa de ser a ação e passa a ser o **critério de objetivo comprovado por evidência**.

O runtime universal segue conceitualmente:

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

Fast paths determinísticos permanecem como otimizações/skills dentro desse runtime; eles não podem retornar `succeeded` por uma semântica paralela de conclusão.

O planner pode sugerir que não há mais trabalho, mas não possui autoridade final para declarar o objetivo concluído. Apenas o verificador de objetivo, usando critérios e evidências, pode autorizar o verdict final.

O Goal Contract permanece pequeno: objetivo original, subobjetivos, critérios, artefatos produzidos e evidências. Não criar microserviços nem reescrever Painel, Central, fila, executores, FAILSAFE, parada de emergência ou providers sem necessidade comprovada.

## D-023 — Execution Receipt não é evidência de efeito

O sucesso técnico de uma chamada ao executor prova somente que uma ação foi enviada/executada conforme seu contrato técnico.

Um `Execution Receipt` não satisfaz sozinho um critério final de objetivo.

Para fechar um critério obrigatório, o Goal Runtime precisa de evidência posterior verificável, preferencialmente observação estruturada ou readback do estado produzido. Enquanto essa evidência não existir, o critério permanece pendente e o objetivo não pode ser marcado como `succeeded`.

## D-024 — Decomposição estruturada precisa cobrir e ancorar o objetivo inteiro

Um provider não pode inventar o próprio efeito e depois usar esse mesmo efeito como critério autorreferente.

Objetivos fora dos intents locais tipados exigem decomposição estruturada antes da primeira ação física. A validação deve preservar, de modo lossless:

- cada ação/cláusula material;
- entidades solicitadas, como aplicativo, URL, consulta e texto;
- cardinalidade e ordem relevantes;
- dependências entre subobjetivos;
- proveniência de targets e artifacts.

Omissão, capability incompatível, URL não ancorada, ordem trocada ou requisito não representável resultam em fail-closed.

## D-025 — Lease e contexto fazem parte da correção do resultado

O Robô renova o lease durante Goals longos e verifica a posse antes/depois de ações e observações. Perda de lease interrompe execução e fallback.

Contexto entre tasks é pequeno, tipado e persistido somente depois que a Central aceita o resultado final. Uma falha ou `409` descarta o contexto diferido para não publicar estado de uma task sem ACK.

## D-026 — Resultado, log, contexto e SQLite são fronteiras de privacidade

Valores brutos necessários ao verifier podem existir apenas em memória durante a execução. Ao atravessar uma fronteira persistente ou visível, URLs, conteúdo digitado, credenciais, exceções e campos arbitrários passam pelo sanitizador comum.

O `TaskStore` também sanitiza diretamente, porque chamadas futuras podem contornar o fluxo normal do Robô.

## D-027 — Navegador nomeado é comprovado pelo pós-estado independente

Receipt, PID efêmero do launcher e título de janela não bastam para comprovar uma busca em Brave/Firefox/Chrome.

O pós-estado exige o mesmo XID ativo, `WM_CLASS` exato, PID/executável da janela e localização lida da omnibox por AT-SPI fora do documento web. Host, path, porta e consulta são comparados à URL construída localmente.

Quando um navegador singleton encerra o launcher ou a janela já está exatamente no estado alvo, `window_changed=false` pode coexistir com sucesso. Isso não transforma o receipt em evidência: a conclusão vem da observação independente do estado final, e o `argv` ainda precisa mostrar que a tentativa correta foi emitida.

## D-028 — Feed estruturado é fallback de busca, não página HTML simulada

O fallback Bing RSS é usado somente depois dos mecanismos HTML e somente quando o próprio documento comprova content-type XML e raiz `rss`/`feed`.

Itens precisam de título e URL HTTP(S). Em Atom, `rel=alternate` ou link sem `rel` representa o resultado; `rel=self` não substitui a URL do item.

## D-029 — Journal durável bloqueia replay cego entre ação física e ACK

Toda ação física/externa executada sob lease passa por um journal durável correlacionado por `task_id + action_key` antes de entrar no backend.

A máquina mínima vigente é:

```text
prepared → in_flight → executed → acknowledged
```

`prepared` significa que a intenção foi persistida, mas o backend ainda não foi chamado. `in_flight` significa que o backend pode ter produzido efeito; para ações não repeat-safe esse estado é deliberadamente ambíguo e fail-closed. `executed` significa apenas que a chamada técnica retornou e um receipt mínimo foi persistido. `acknowledged` significa que a Central aceitou o estado terminal da task.

O journal **não possui estado `verified`** e não pode satisfazer critérios do objetivo. Percepção independente, EvidenceRecord e GoalVerifier continuam sendo a única cadeia autorizada a produzir `succeeded`.

`action_key` é um fingerprint task-scoped de `action + target`, sem persistir o target bruto. A mesma ação+target na mesma task produz a mesma identidade; retries e reclaims não recebem um contador implícito que permita fabricar uma segunda emissão física. Se uma capacidade futura precisar repetir legitimamente duas ações idênticas, ela deverá fornecer identidade estável explícita no contrato.

Apenas operações classificadas explicitamente como repeat-safe podem ser repetidas quando o journal já registra entrada/execução. Nesta fase, essa categoria é limitada a `active_window` e `capture_screen`.

Tasks legadas já iniciadas sem journal são ambíguas e devem falhar fechadas na migração, em vez de voltar para a fila. Tasks legadas nunca iniciadas podem aderir ao journal v1 quando forem claimadas.

O ACK da Central torna o journal elegível a cleanup, mas não precisa ser atômico com o mundo físico. Se houver crash depois da terminalização da task e antes de marcar o journal como `acknowledged`, a Central reconcilia rows de tasks terminais no próximo startup. Cleanup automático só remove rows `acknowledged` depois da retenção configurável.

O journal persiste somente identidade, estado, timestamps e receipt mínimo sanitizado. Texto integral digitado, screenshots e URLs completas não fazem parte do contrato persistente.

## D-030 — Atualização e validação local são interfaces oficiais e não destrutivas

A rotina local recorrente deve ser reduzida aos comandos oficiais `atualizar-robo` e `validar-robo`, em vez de depender de uma sequência manual extensa de Git, ambiente e testes.

`atualizar-robo` pode atualizar somente por fast-forward. Se houver working tree suja, commits locais não publicados, origin inesperado ou qualquer condição que exija reescrita/descarte, o comando deve parar e preservar o estado existente. Não é permitido automatizar `git reset --hard`, `git clean`, rebase ou descarte silencioso como forma normal de atualização.

`validar-robo` deve separar a validação automática da prova física. Ele verifica código, suíte, ambiente e pré-requisitos Linux/X11, mas não executa mouse/teclado/navegador como se isso fosse evidência física. Somente depois de um resultado local verde começa o smoke real, um cenário por vez.

## D-031 — Fault injection físico é local-only, one-shot e não simula efeito

Crash testing do Durable Journal deve usar checkpoints explícitos e reproduzíveis no fluxo real, em vez de depender de o operador tentar matar manualmente o processo no instante correto.

O fault injection fica desarmado por padrão e só pode ser armado localmente. Nesta fase não existe endpoint no Painel/Central para armá-lo. O armamento é persistido em `runtime/`, consumido atomicamente antes do crash proposital e não se rearma no restart.

Checkpoints vigentes são `after_prepare`, `after_in_flight`, `after_backend`, `after_executed`, `before_ack` e `after_ack`. O controlador encerra somente o processo do Robô; backend físico, SQLite, journal, lease, reclaim, percepção e restart continuam reais.

O evento persistente de fault injection contém apenas checkpoint, PID e identificadores técnicos permitidos. Texto bruto do objetivo/target e credenciais não fazem parte desse registro.

Essa infraestrutura não altera a autoridade do GoalVerifier nem a semântica do journal. Em especial, um `in_flight` de ação não repeat-safe continua ambíguo e fail-closed, mesmo quando o teste sabe em qual ponto o processo foi encerrado; recovery deve decidir pelo estado durável, não por conhecimento externo do harness.

## D-032 — Direção estratégica: Operador Digital Autônomo Multimodal

A próxima evolução do produto é transformar o Robô em um **Operador Digital Autônomo Multimodal**: um sistema que recebe objetivos em linguagem natural, decompõe o trabalho necessário, executa ações reais no computador e em serviços digitais, verifica o resultado e mantém diálogo operacional com o usuário.

O alvo de produto inclui operar tarefas que hoje exigem intervenção manual entre ChatGPT e o computador, como trabalhar com projetos locais, Git/GitHub, navegador, Cloudflare, Vercel, Render e outros serviços, escolhendo a interface de execução mais adequada disponível — API/MCP, CLI/terminal, automação web estruturada ou, quando necessário, mouse e teclado.

Voz bidirecional, contexto conversacional operacional, gestão segura de credenciais e uma futura ponte ChatGPT → Robô fazem parte da direção de produto a ser debatida, mas **não estão aprovadas aqui como arquitetura ou escopo fechado de implementação**.

O nome de trabalho da próxima fase é `PM-UNIVERSAL-OPERATOR-001 — Natural Language → Real Computer Work`. Esse nome é provisório até o planejamento com o MCF.

Antes de implementação, o escopo, arquitetura, capacidades, critérios de aceitação, riscos, sequência de entrega e testes devem ser debatidos e planejados com o MCF. Até esse planejamento ser aprovado, esta decisão representa direção estratégica, não autorização para alterar a arquitetura nem iniciar código da nova fase.

A nova autonomia deve crescer sobre as garantias já comprovadas, preservando Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente, EvidenceRecord e GoalVerifier como única autoridade de conclusão. Novas capacidades físicas ou externas também precisam manter identidade durável adequada para retries/reclaims e não podem reintroduzir replay cego.