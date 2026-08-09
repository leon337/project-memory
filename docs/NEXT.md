# NEXT

## 1. Concluir a validação física de segurança

Percepção, mouse, abertura de aplicativo, digitação, sincronização de foco e uma tecla permitida (`Enter`) já foram validados no Linux real.

Próximos testes, em passos pequenos:

1. executar o diagnóstico pelo botão do Painel;
2. validar o `FAILSAFE` físico;
3. validar a parada de emergência real pelo Painel e a liberação consciente do bloqueio.

Critério de conclusão: mecanismos de diagnóstico e parada devem funcionar fisicamente sem bypass da Policy Layer.

## 2. Fechar o ciclo de operação e melhorar o design do Painel

Validar o uso normal sem depender de vários terminais manuais e corrigir o desconforto visual observado no uso real:

- ligar, parar e reiniciar Central e Robô pelo Painel;
- confirmar estados corretos após cada transição;
- testar o Laboratório com um comando conhecido, confirmando explicação sem execução automática de shell;
- reduzir o fluxo diário ao atalho `Painel do Robô` e à interface Web local;
- revisar o tema atual para reduzir brilho e fadiga visual, com aparência de menor luminosidade, melhor hierarquia e contraste;
- validar visualmente o novo design no computador real antes de considerar o Painel pronto para uso diário.

Critério de conclusão: o usuário deve conseguir administrar e diagnosticar o ciclo básico pelo Painel sem manter terminais separados para Central e Robô e sem desconforto causado pelo tema atual.

## 3. Ativar o primeiro planner por IA

Depois da validação física e operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
