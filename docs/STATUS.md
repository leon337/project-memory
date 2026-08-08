# STATUS

## Objetivo atual

Construir um agente autônomo capaz de operar o computador do usuário como um operador digital, sempre dentro das permissões concedidas pelo usuário e pelo sistema operacional.

O objetivo final continua incluindo:

- mouse e teclado;
- aplicativos;
- navegador e sites;
- sessões autenticadas sem expor credenciais ao modelo;
- percepção da tela;
- câmera quando explicitamente autorizada;
- tarefas compostas em vários passos;
- controle remoto por Web, WhatsApp, Telegram e Instagram.

## Estado verificável agora

O repositório `leon337/project-memory` deixou de conter apenas documentação e possui um primeiro MVP implementado no branch `main`.

### Implementado

- pacote Python 3.11+ em `src/context_anchor`;
- Control Plane em FastAPI;
- painel Web local;
- fila durável de tarefas em SQLite;
- autenticação separada por token para usuário e agente local;
- agente local que consulta o Control Plane por HTTP polling;
- planner determinístico inicial;
- Policy Layer com allowlist;
- automação de navegador com Playwright/Chromium;
- verificação de URL final, título e status HTTP;
- comandos do MVP: `abrir <site>` e `pesquisar/buscar <termo>`;
- bloqueio de localhost, `.local`, IPs privados/loopback e esquemas não HTTP(S);
- `.env.example` sem segredos reais;
- testes unitários da política e do armazenamento;
- teste de integração do Control Plane;
- workflow GitHub Actions para compilação e `pytest`;
- README com instalação e operação.

### Arquitetura técnica escolhida para o MVP

- alvo inicial: desktop Linux;
- linguagem: Python 3.11+;
- Control Plane: FastAPI;
- persistência: SQLite;
- comunicação servidor → agente: polling HTTP autenticado;
- automação de navegador: Playwright + Chromium;
- modelo de IA: ainda não escolhido; o MVP usa planner determinístico para validar o ciclo operacional antes de integrar um LLM.

## Validação

- O primeiro workflow de CI após a criação do pipeline concluiu com sucesso.
- Um segundo workflow foi disparado após a inclusão do teste de integração do Control Plane e estava em execução durante esta atualização.
- Uma tentativa de clonar o repositório dentro do ambiente de execução desta sessão falhou porque esse ambiente não conseguiu resolver `github.com`; por isso a validação automatizada foi delegada ao GitHub Actions. Isso não indica falha do código do projeto.

## Ainda não implementado

- controle de mouse e teclado;
- percepção de tela;
- árvore de acessibilidade;
- abertura/controle genérico de aplicativos;
- câmera;
- planner por modelo de IA;
- memória operacional de tarefas longas;
- confirmação humana para ações sensíveis;
- emergency stop independente;
- Control Plane publicado para acesso remoto;
- TLS, pareamento de dispositivo e autenticação forte para Internet;
- WhatsApp;
- Telegram;
- Instagram.

## Limite operacional atual

O servidor escuta `127.0.0.1` por padrão e esta versão não deve ser exposta diretamente à Internet.

O MVP não executa shell arbitrário, não contorna login/MFA e não recebe senhas pelo modelo.
