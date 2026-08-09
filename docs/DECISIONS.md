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

## D-010 — Planner antes do LLM

O planner ativo permanece determinístico até a validação física do caminho de execução.

Foi criado um contrato provider-agnostic de saída estruturada para preparar a integração futura, mas nenhum modelo de IA está ativado ainda.

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

## D-018 — Contrato estruturado para planners futuros

Um provedor de IA futuro deverá devolver somente uma ação pertencente ao esquema estruturado conhecido pelo sistema.

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
- o painel Web terá o título **Central do Robô**.

Os comandos principais para uso humano são:

- `central` — liga a Central;
- `robo` — liga o Robô local;
- `parar-robo` — controla a parada de emergência;
- `diagnostico-robo` — verifica o ambiente do computador.

Os comandos técnicos antigos `context-anchor-control`, `context-anchor-agent`, `context-anchor-stop` e `context-anchor-doctor` permanecem como aliases de compatibilidade para não quebrar instalações, documentação antiga ou diagnóstico de versões anteriores.

Os nomes técnicos internos podem continuar existindo no código e na documentação arquitetural quando forem úteis para aprendizado, preferencialmente apresentados após o nome intuitivo, por exemplo: `Central (Control Plane)` e `Robô local (local agent)`.

## D-021 — Painel do Robô como centro de operação e aprendizado

Antes de ampliar os testes manuais de desktop, será criado um **Painel do Robô** local e independente da Central.

O painel terá duas funções simultâneas:

1. operar e configurar o sistema sem depender de vários terminais;
2. ensinar o usuário o que cada configuração, comando e processo faz.

O Painel do Robô deverá, progressivamente, oferecer:

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

O Painel do Robô será um processo local separado da Central para continuar disponível mesmo quando a Central ou o Robô forem desligados ou reiniciados.

## D-022 — Sequências de desktop devem esperar prontidão e foco observáveis

A conclusão de uma ação de interface não pode significar apenas que um comando foi enviado ao sistema operacional.

Ao encadear ações como `abrir aplicativo` seguido de `digitar`, o executor deve esperar a janela ficar pronta e ganhar foco suficiente para a próxima ação. Um atraso fixo curto pode ser usado apenas como fallback de MVP, não como evidência de prontidão.

A digitação deve registrar em qual janela ativa foi executada e não deve ser tratada como verificada apenas porque as teclas foram enviadas. Quando o alvo esperado puder ser conhecido, foco e resultado devem ser confirmados antes de marcar a etapa como concluída.