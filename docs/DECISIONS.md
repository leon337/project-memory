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

Control Plane e agente local se comunicam por HTTP polling autenticado.

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

O Control Plane escuta apenas localhost por padrão.

Usuário e agente têm credenciais separadas. Ações não reconhecidas ou fora da allowlist são bloqueadas.

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

O emergency stop deve continuar funcionando mesmo que o planner, a comunicação remota ou as credenciais do agente estejam com problema.

A implementação local usa sentinel persistente, PID e identidade de processo Linux antes de enviar `SIGTERM`.

O sentinel precisa ser limpo conscientemente antes de o agente voltar a executar.

## D-017 — Leases para propriedade de tarefa

Uma tarefa em execução pertence temporariamente a uma execução específica por meio de um lease e token aleatório.

Resultados só são aceitos enquanto esse lease ainda for o proprietário atual. Tarefas abandonadas podem voltar para a fila e existe limite de tentativas para impedir loop infinito.

## D-018 — Contrato estruturado para planners futuros

Um provedor de IA futuro deverá devolver somente uma ação pertencente ao esquema estruturado conhecido pelo sistema.

O esquema não possui ação de shell nem campos livres para comandos de ferramenta. Mesmo uma ação estruturalmente válida continua sujeita à Policy Layer antes da execução.
