# DECISIONS

## D-001 — Objetivo principal

O projeto terá como objetivo construir um agente capaz de funcionar como operador digital do computador do usuário.

O agente deverá ser capaz de receber um objetivo e executar múltiplas ações até concluí-lo.

## D-002 — Controle do computador

O sistema deverá evoluir para suportar:

- mouse;
- teclado;
- aplicativos;
- navegador;
- sites;
- sessões autenticadas;
- câmera autorizada.

## D-003 — Operação remota

O agente deverá poder receber comandos remotamente.

Canais desejados:

- Web;
- WhatsApp;
- Telegram;
- Instagram.

As integrações não precisam fazer parte simultaneamente do primeiro MVP.

## D-004 — Autonomia

O objetivo é permitir alto grau de autonomia.

“Controle irrestrito” significa acesso às capacidades concedidas pelo usuário e pelo sistema operacional, e não bypass de mecanismos de autenticação ou segurança.

A arquitetura deverá permitir restringir determinadas categorias de ação.

## D-005 — Credenciais

Senhas, tokens e outras credenciais não devem ser armazenados diretamente no código, prompts, logs ou repositório.

O gerenciamento de credenciais deverá ser separado do mecanismo de raciocínio do agente.

## D-006 — Controle observável

O agente deverá verificar o resultado das ações executadas e manter histórico suficiente para diagnosticar falhas.

## D-007 — Primeiro alvo operacional

O primeiro alvo do MVP será desktop Linux.

A arquitetura deverá evitar acoplamentos desnecessários ao sistema operacional para permitir suporte posterior a outros ambientes.

## D-008 — Stack do MVP

O núcleo inicial será implementado em Python 3.11+.

O Control Plane usará FastAPI e a persistência inicial usará SQLite.

A comunicação entre Control Plane e agente local será HTTP polling autenticado. Essa escolha reduz complexidade no primeiro teste vertical e poderá ser substituída posteriormente sem alterar o contrato de tarefa.

## D-009 — Automação de navegador

O primeiro executor real será Playwright com Chromium.

Automação estruturada do navegador terá prioridade sobre visão computacional e coordenadas de mouse quando DOM ou APIs apropriadas estiverem disponíveis.

## D-010 — Planner antes do LLM

O primeiro planner será determinístico e limitado aos comandos necessários para provar o ciclo operacional.

Um modelo de IA só será integrado depois que o caminho comando → política → execução → verificação estiver validado. O provedor do modelo permanece em aberto.

## D-011 — Web primeiro

A interface Web será o primeiro canal funcional.

WhatsApp, Telegram e Instagram só serão adicionados depois que o núcleo local estiver validado, para evitar que problemas de mensageria escondam falhas do agente.

## D-012 — Seguro por padrão

O Control Plane deverá escutar apenas localhost por padrão e não será exposto diretamente à Internet no MVP.

Usuário e agente terão credenciais separadas.

Ações não reconhecidas ou fora da allowlist serão bloqueadas em vez de executadas por tentativa.

## D-013 — Sem shell arbitrário no MVP

O primeiro MVP não oferecerá execução genérica de comandos de shell recebidos remotamente.

Novas capacidades de desktop serão introduzidas como ações tipadas e autorizadas pela Policy Layer, com validação e auditoria próprias.
