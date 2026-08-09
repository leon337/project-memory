# DECISIONS

## D-001 — Objetivo principal

O projeto terá como objetivo construir um agente capaz de funcionar como operador digital do computador do usuário.

O agente deverá ser capaz de receber um objetivo e executar múltiplas ações até concluí-lo.

## D-002 — Controle do computador

O sistema deverá evoluir para suportar mouse, teclado, aplicativos, navegador, sites, sessões autenticadas e câmera autorizada.

## D-003 — Operação remota

O agente deverá poder receber comandos por Web, WhatsApp, Telegram e Instagram.

Esses canais não precisam entrar simultaneamente no MVP.

## D-004 — Autonomia

O objetivo é permitir alto grau de autonomia.

“Controle irrestrito” significa acesso às capacidades concedidas pelo usuário e pelo sistema operacional, e não bypass de autenticação ou mecanismos de segurança.

## D-005 — Credenciais

Senhas, tokens e outras credenciais não devem ser armazenados diretamente no código, prompts, logs ou repositório.

O gerenciamento de credenciais deverá permanecer separado do mecanismo de raciocínio.

## D-006 — Controle observável

O agente deverá verificar resultados e manter histórico suficiente para diagnosticar falhas.

## D-007 — Primeiro alvo operacional

O primeiro alvo é desktop Linux.

O backend físico inicial foi desenhado para Linux/X11. Outros ambientes serão adicionados sem alterar o contrato de ações quando possível.

## D-008 — Stack do MVP

O núcleo usa Python 3.11+, FastAPI e SQLite.

A Central e o Robô local se comunicam por HTTP polling autenticado.

## D-009 — Automação de navegador

Playwright com Chromium é o primeiro executor de navegador.

Automação estruturada tem prioridade sobre coordenadas visuais quando DOM/API apropriada estiver disponível.

## D-010 — Planner determinístico permanece como caminho local e fallback

O `DeterministicPlanner` permanece disponível mesmo com o planner multi-provider ativo.

Pedidos que já pertencem ao vocabulário determinístico devem ser resolvidos localmente antes de chamar uma API externa. Isso reduz latência, economiza quota e mantém um caminho previsível de teste e recuperação.

Pedidos que o parser determinístico não entende podem seguir para o `MultiProviderPlanner`, desde que as credenciais necessárias estejam configuradas localmente.

## D-011 — Web primeiro

A interface Web permanece o primeiro canal funcional.

WhatsApp, Telegram e Instagram entram depois que o núcleo local estiver validado e o acesso remoto estiver protegido.

## D-012 — Seguro por padrão

A Central escuta apenas localhost por padrão.

Usuário e Robô têm credenciais separadas. Ações não reconhecidas ou fora da allowlist são bloqueadas.

## D-013 — Sem shell arbitrário

O sistema não oferece execução genérica de shell recebida remotamente.

Novas capacidades entram como ações tipadas, validadas e autorizadas pela Policy Layer.

## D-014 — Desktop desativado por padrão

A existência do executor de desktop não implica permissão para usá-lo.

O controle físico fica bloqueado até `CONTEXT_ANCHOR_DESKTOP_ENABLED=true` ser configurado localmente.

Isso permite instalar, testar CI e operar apenas o navegador sem habilitar mouse/teclado por acidente.

## D-015 — Aplicativos por allowlist fixa

Pedidos remotos para abrir aplicativos são resolvidos por ids conhecidos para uma lista fixa de executáveis.

O sistema não aceita caminho de executável ou argumentos de shell fornecidos livremente pelo comando remoto. A abertura usa `shell=False`.

## D-016 — Emergency stop independente do planner

O emergency stop deve continuar funcionando mesmo que o planner, a comunicação remota ou as credenciais do Robô estejam com problema.

A implementação local usa sentinel persistente, PID e identidade de processo Linux antes de enviar `SIGTERM`.

O sentinel precisa ser limpo conscientemente antes de o Robô voltar a executar.

## D-017 — Leases para propriedade de tarefa

Uma tarefa em execução pertence temporariamente a uma execução específica por meio de um lease e token aleatório.

Resultados só são aceitos enquanto esse lease ainda for o proprietário atual. Tarefas abandonadas podem voltar para a fila e existe limite de tentativas para impedir loop infinito.

## D-018 — Contrato estruturado para planners de IA

Um provedor de IA deve devolver somente uma ação pertencente ao esquema estruturado conhecido pelo sistema.

O esquema não possui ação de shell nem campos livres para comandos de ferramenta. Mesmo uma ação estruturalmente válida continua sujeita à Policy Layer antes da execução.

## D-019 — Construção também deve ensinar operação e diagnóstico

Durante o desenvolvimento, cada etapa prática deve ser explicada em linguagem simples para que o usuário aprenda a operar, diagnosticar e recuperar o sistema sem depender permanentemente do assistente.

Ao orientar comandos ou testes, a explicação deve incluir, quando relevante:

- o que o comando faz;
- por que ele é necessário;
- qual resultado é esperado;
- como reconhecer uma falha;
- qual princípio técnico está sendo aprendido.

A prioridade durante o MVP é aprender o funcionamento real do sistema junto com a implementação, sem transformar detalhes não bloqueantes em burocracia.

## D-020 — Terminologia e comandos didáticos

Na comunicação com o usuário e na interface visível, os nomes principais devem ser intuitivos.

- `Control Plane` será apresentado como **Central**.
- `local agent` será apresentado como **Robô local** ou apenas **Robô**.
- a interface principal será apresentada como **Painel do Robô**.

Os comandos principais para uso humano são:

- `central` — liga a Central;
- `robo` — liga o Robô local;
- `parar-robo` — controla a parada de emergência;
- `diagnostico-robo` — verifica o ambiente do computador.

Os comandos técnicos antigos `context-anchor-control`, `context-anchor-agent`, `context-anchor-stop` e `context-anchor-doctor` permanecem como aliases de compatibilidade para não quebrar instalações, documentação antiga ou diagnóstico de versões anteriores.

Os nomes técnicos internos podem continuar existindo no código e na documentação arquitetural quando forem úteis para aprendizado, preferencialmente apresentados após o nome intuitivo, por exemplo: `Central (Control Plane)` e `Robô local (local agent)`.

## D-021 — Painel do Robô como centro de operação e aprendizado

O **Painel do Robô** local e independente da Central é o centro de operação e aprendizado.

O painel tem duas funções simultâneas:

1. operar e configurar o sistema sem depender de vários terminais;
2. ensinar o usuário o que cada configuração, comando e processo faz.

O Painel do Robô deve oferecer progressivamente:

- status visual da Central, Robô, desktop e parada de emergência;
- botões para ligar, desligar e reiniciar Central e Robô;
- habilitação/desabilitação de capacidades como navegador, screenshot, mouse, teclado e aplicativos;
- configurações expostas por controles visuais em vez de edição manual de `.env` quando possível;
- diagnóstico do ambiente e dependências;
- histórico de tarefas e resultados;
- logs separados e identificados por componente;
- testes guiados das capacidades do Robô;
- área de aprendizado que explique comandos, resultado esperado e erros comuns;
- campo para receber comandos de manutenção fornecidos durante o desenvolvimento, com visualização e explicação antes da execução.

O campo de comandos do painel não será um shell remoto irrestrito. Ele deverá executar somente operações locais explicitamente suportadas pelo modo de desenvolvimento, ou apresentar o comando para cópia/execução manual quando estiver fora dessa lista.

O Painel do Robô permanece um processo local separado da Central para continuar disponível mesmo quando a Central ou o Robô forem desligados ou reiniciados.

## D-022 — Sequências de desktop devem esperar prontidão e foco observáveis

A conclusão de uma ação de interface não pode significar apenas que um comando foi enviado ao sistema operacional.

Ao encadear ações como `abrir aplicativo` seguido de `digitar`, o executor deve esperar a janela ficar pronta e ganhar foco suficiente para a próxima ação. Um atraso fixo curto pode ser usado apenas como fallback de MVP, não como evidência de prontidão.

A digitação deve registrar em qual janela ativa foi executada e não deve ser tratada como verificada apenas porque as teclas foram enviadas. Quando o alvo esperado puder ser conhecido, foco e resultado devem ser confirmados antes de marcar a etapa como concluída.

## D-023 — Conforto visual é requisito do Painel

O tema visual do Painel do Robô não deve usar grandes áreas claras como padrão, pois isso foi considerado cansativo em uso real.

O padrão visual do Painel será **ultra escuro**, com fundo próximo de preto, superfícies em grafite/azul muito escuro e brilho reduzido. Entre alternativas visuais aceitáveis, deve-se preferir a opção de menor luminosidade, desde que preserve leitura clara dos textos, estados, alertas e controles de segurança.

A revisão visual deve melhorar conjuntamente hierarquia, contraste, tamanho e legibilidade dos textos, uso do espaço e aparência profissional. Configurações e Laboratório devem seguir o mesmo sistema visual da Visão geral, sem parecer páginas vazias ou desconectadas.

A melhoria visual deve preservar destaque inequívoco para estados positivos, falhas e parada de emergência. O design só é considerado concluído depois de carregado e aprovado visualmente no computador real.

## D-024 — Controles operacionais e logs devem refletir realidade observável

Controles de operação não devem funcionar como botões estáticos que apenas disparam comandos. O Painel deve mostrar no próprio controle o estado atual do componente e adaptar a próxima ação disponível a esse estado.

A Central deve distinguir pelo menos os estados **desligada**, **ligada e gerenciada pelo Painel** e **ligada fora do Painel**. O Robô e a parada de emergência também devem refletir seu estado real antes de oferecer ações.

Uma área chamada **Logs ao vivo** ou equivalente só pode ser apresentada como tal quando exibir eventos reais produzidos pela aplicação. Painel, Central e Robô devem gravar telemetria persistente por componente, com timestamp e nível, independentemente de terem sido iniciados pelo Painel.

A telemetria não deve registrar credenciais. Para reduzir exposição desnecessária, os eventos estruturados devem preferir ids de tarefa, estados, transições e tipos de erro em vez de copiar o texto bruto enviado pelo usuário.

## D-025 — FAILSAFE de desktop deve ser explícito e independente do PyAutoGUI

O FAILSAFE nativo do PyAutoGUI permanece habilitado como defesa adicional, mas não será considerado mecanismo de segurança suficiente por si só porque falhou no primeiro teste físico real.

Antes de ações de entrada física de mouse ou teclado, o backend do Robô deve verificar diretamente a posição atual do ponteiro. Uma zona de segurança de 20 pixels nos quatro cantos da tela funciona como gesto local de interrupção.

Se o ponteiro estiver nessa zona, a ação deve ser recusada antes de mover o mouse, clicar, digitar ou pressionar tecla. A falha deve subir como `DesktopFailsafeTriggered`, fazendo a tarefa terminar como `failed` e permitindo que a telemetria registre a interrupção.

Esse mecanismo complementa, mas não substitui, a parada de emergência persistente. O FAILSAFE serve para interromper a próxima entrada física imediatamente; a parada de emergência continua sendo o mecanismo para encerrar e bloquear o Robô até liberação consciente.

## D-026 — Planner por IA será multi-provider com roteamento inteligente e consciente de quota

O planner por IA não dependerá de um único provedor. A arquitetura segue um modelo **multi-provider**, com um roteador local responsável por escolher o provedor/modelo adequado a cada chamada.

O conjunto inicial escolhido é:

- **Z.AI / GLM-4.7-Flash** — principal candidato para reasoning e decisões mais complexas;
- **Cloudflare Workers AI** — principal candidato para decisões simples, frequentes e bursts, usando modelos eficientes para preservar o budget diário de neurons;
- **Google Gemini** — provedor complementar para planejamento textual, futura multimodalidade/visão e fallback quando apropriado.

A distribuição não será round-robin nem balanceamento igual. O roteador deverá considerar, no mínimo:

1. capacidade exigida pela tarefa, como texto, reasoning, visão e tools;
2. quota/budget disponível conhecido ou estimado;
3. concorrência permitida;
4. latência recente;
5. erros recentes, especialmente `429`, timeout e `5xx`;
6. estado de cooldown/circuit breaker do provedor;
7. preferência por preservar recursos mais caros ou escassos para tarefas que realmente precisem deles.

Quando um provedor estiver indisponível, limitado ou inadequado para a tarefa, o roteador poderá selecionar outro provedor compatível sem alterar o contrato interno do Robô.

O roteador seleciona apenas o **planner**. Ele não pode contornar a Policy Layer, o FAILSAFE, a parada de emergência ou as validações dos executores.

Fallback de provedor deve acontecer antes da execução física ou depois de uma falha comprovadamente anterior à execução. Uma ação física já executada não deve ser repetida automaticamente apenas porque a chamada seguinte de IA falhou; verificação e idempotência continuam obrigatórias.

O `DeterministicPlanner` permanece disponível como caminho local e fallback técnico.

SiliconFlow continua como candidato opcional futuro, mas não entra no conjunto inicial até que os limites reais dos modelos gratuitos sejam comprovados na conta.

Todas as chaves de API permanecerão somente em configuração local/variáveis de ambiente e nunca em código, Git, logs ou prompts.

## D-027 — Gemini usa o SDK oficial `google-genai`

A integração vigente do Gemini no planner usa o SDK oficial **`google-genai`** e `client.models.generate_content(...)`, em vez de construir manualmente o payload REST.

Essa decisão foi tomada depois de comparar o `project-memory` com o repositório `leon337/meu_primeiro_agente`, onde esse padrão já está implementado e usado com `gemini-3.6-flash`.

O modelo padrão do planner Gemini é `gemini-3.6-flash`. O SDK recebe `GenerateContentConfig` com instrução do sistema, `response_mime_type=application/json` e o `ACTION_SCHEMA` do projeto.

A resposta do SDK, seja por `parsed` ou texto JSON, continua obrigada a validar como `StructuredAction`. O uso do SDK não dá ao Gemini acesso direto a ferramentas, mouse, teclado, navegador ou shell; a ação proposta ainda passa pela Policy Layer, FAILSAFE e demais proteções locais.
