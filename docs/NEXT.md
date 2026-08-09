# NEXT

## 1. Concluir a validação física de segurança e teclado

O caminho de percepção, mouse, abertura de aplicativo e digitação já foi validado no Linux real.

Próximos testes, em passos pequenos:

1. validar uma tecla permitida em um aplicativo controlado;
2. executar o diagnóstico pelo botão do Painel;
3. validar o `FAILSAFE` físico;
4. validar a parada de emergência real pelo Painel e a liberação consciente do bloqueio.

Critério de conclusão: teclado e mecanismos de parada devem funcionar fisicamente sem enviar entrada para a janela errada e sem bypass da Policy Layer.

## 2. Fechar o ciclo de operação pelo Painel

Validar o uso normal sem depender de vários terminais manuais:

- ligar, parar e reiniciar Central e Robô pelo Painel;
- confirmar estados corretos após cada transição;
- testar o Laboratório com um comando conhecido, confirmando explicação sem execução automática de shell;
- reduzir o fluxo diário ao atalho `Painel do Robô` e à interface Web local.

Critério de conclusão: o usuário deve conseguir administrar e diagnosticar o ciclo básico pelo Painel sem manter terminais separados para Central e Robô.

## 3. Ativar o primeiro planner por IA

Depois da validação física e operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
