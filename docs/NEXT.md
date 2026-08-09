# NEXT

## 1. Fechar a revisão ultra escura do Painel

A segunda revisão visual já foi implementada, baixada no computador alvo, carregada pelo atalho do desktop e confirmada visualmente nas telas **Visão geral**, **Configurações** e **Laboratório**.

Próximo passo:

1. obter a confirmação final do usuário sobre conforto, legibilidade, contraste e organização.

Critério de conclusão: o usuário deve aprovar o tema ultra escuro para uso prolongado e nenhum controle funcional pode ter sido prejudicado pela revisão visual.

## 2. Concluir segurança e operação física

Depois da aprovação visual:

- validar o `FAILSAFE` físico;
- validar a parada de emergência real pelo Painel e a liberação consciente do bloqueio;
- ligar, parar e reiniciar Central e Robô pelo Painel;
- confirmar estados corretos após cada transição;
- testar o Laboratório com um comando conhecido;
- reduzir o fluxo diário ao atalho `Painel do Robô` e à interface Web local.

Critério de conclusão: mecanismos de parada, operação e diagnóstico devem funcionar fisicamente sem bypass da Policy Layer e sem dependência normal de terminais separados.

## 3. Ativar o primeiro planner por IA

Depois da validação física e operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
