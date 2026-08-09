# NEXT

## 1. Validar a segunda revisão ultra escura do Painel

A segunda revisão visual já está implementada no `main` com fundo próximo de preto, tipografia mais legível, melhor hierarquia, melhor uso do espaço e layouts específicos para Visão geral, Configurações e Laboratório.

Próximos passos, em ordem:

1. executar `git pull` no computador alvo;
2. reiniciar apenas o processo do **Painel do Robô** pelo atalho do desktop;
3. validar visualmente **Visão geral**, **Configurações** e **Laboratório**;
4. confirmar conforto, legibilidade, contraste, organização e funcionamento dos controles.

Critério de conclusão: o usuário deve aprovar o tema ultra escuro para uso prolongado e nenhum controle funcional pode ser prejudicado pela revisão visual.

## 2. Concluir segurança e operação física

Depois da validação visual:

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
