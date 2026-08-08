# ARCHITECTURE

## Visão geral

O sistema será dividido entre um agente executando no computador e uma camada remota responsável por receber comandos.

Fluxo conceitual:

Usuário
↓
Web / WhatsApp / Telegram / Instagram
↓
Control Plane
↓
Autenticação
↓
Orquestrador
↓
Agente local
↓
Percepção → Raciocínio → Ação → Verificação
↓
Computador

## 1. Agente local

Processo executado no computador controlado.

Responsabilidades:

- observar o estado do computador;
- capturar informações da tela;
- identificar aplicações e interfaces;
- controlar mouse;
- controlar teclado;
- abrir aplicações;
- manipular arquivos autorizados;
- operar navegador;
- executar tarefas solicitadas;
- reportar resultados ao servidor.

## 2. Perception Layer

Responsável por transformar o estado visual do computador em informações utilizáveis pelo agente.

Possíveis fontes:

- screenshots;
- árvore de acessibilidade;
- informações das janelas;
- DOM do navegador quando disponível;
- APIs específicas de aplicativos.

A arquitetura deverá evitar depender exclusivamente de visão computacional quando uma interface estruturada estiver disponível.

## 3. Action Layer

Camada responsável pelas ações reais no computador.

Capacidades previstas:

- mouse;
- teclado;
- gerenciamento de janelas;
- abertura de aplicativos;
- navegador;
- arquivos;
- execução de comandos previamente permitidos;
- câmera quando explicitamente habilitada.

## 4. Agent Core

Executará um ciclo orientado a objetivo:

Objetivo
→ observar
→ planejar
→ executar ação
→ observar resultado
→ verificar progresso
→ escolher próxima ação
→ concluir ou continuar

O agente não deverá assumir que uma ação funcionou apenas porque tentou executá-la.

## 5. Browser Layer

O navegador deverá possuir integração própria.

Preferência arquitetural:

API/DOM
→ automação estruturada
→ acessibilidade
→ visão + mouse/teclado como fallback

Isso evita usar coordenadas da tela quando uma forma mais confiável estiver disponível.

## 6. Credential Layer

Credenciais não deverão ser colocadas:

- no código;
- nos prompts;
- nos logs;
- no Git;
- diretamente no modelo de IA.

O agente deverá utilizar um mecanismo específico de gerenciamento de credenciais ou sessões existentes.

Como o repositório atualmente é público, nenhum segredo poderá ser armazenado nele.

## 7. Policy Layer

Antes de executar uma ação, o sistema deverá poder determinar:

- se o agente possui permissão;
- se exige confirmação humana;
- se pode executar autonomamente;
- se deve bloquear a operação.

A arquitetura deve permitir diferentes níveis de autonomia.

## 8. Audit Layer

Ações relevantes deverão gerar registro contendo, quando aplicável:

- comando recebido;
- objetivo;
- ações executadas;
- resultado;
- horário;
- canal de origem;
- erros.

## 9. Emergency Stop

O usuário deverá possuir uma forma independente de interromper imediatamente a execução do agente.

Esse mecanismo não poderá depender do próprio modelo de IA decidir parar.

## 10. Control Plane

Camada responsável pela comunicação entre o usuário e o computador.

Deverá fornecer:

- autenticação;
- autorização;
- gerenciamento de sessões;
- envio de comandos;
- acompanhamento da execução;
- histórico;
- cancelamento de tarefas.

## 11. Channel Adapters

Cada canal deverá ser desacoplado do núcleo do agente.

Estrutura prevista:

Web Adapter
WhatsApp Adapter
Telegram Adapter
Instagram Adapter
        ↓
Command Gateway
        ↓
Agent Core

Dessa maneira novos canais poderão ser adicionados sem alterar o mecanismo que controla o computador.

## 12. Princípio local-first

O controle físico do computador deverá permanecer no agente local.

Serviços externos enviam intenções e recebem resultados, mas não deverão possuir controle direto dos dispositivos sem passar pelo agente local e pelas políticas de autorização.
