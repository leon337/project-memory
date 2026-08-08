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
