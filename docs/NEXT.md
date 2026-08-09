# NEXT

## 1. Validar telemetria real de Central e Robô

A terceira revisão do Painel já foi carregada no computador alvo. Os **Controles de estado** foram validados fisicamente para Central, Robô e Emergência, e o log real do **Painel** já apareceu em **Logs reais da aplicação**.

Próximos passos, em ordem:

1. encerrar uma vez a **Central** que ainda está rodando fora do Painel e iniciá-la pelo próprio Painel com o código novo;
2. confirmar que o controle da Central muda de **Ligada fora do Painel** para estado gerenciado pelo Painel e que eventos reais aparecem no filtro **Central**;
3. reiniciar o **Robô** com o código novo e confirmar eventos reais no filtro **Robô**;
4. observar se os controles mudam corretamente durante ligar, parar e reiniciar.

Critério de conclusão: os três componentes devem produzir telemetria real identificada por origem, e os controles devem refletir corretamente todas as transições observadas.

## 2. Concluir segurança e operação física

Depois da validação da telemetria:

- validar o `FAILSAFE` físico;
- validar a parada de emergência real pelo Painel e a liberação consciente do bloqueio;
- completar o ciclo ligar/parar/reiniciar Central e Robô pelo Painel;
- confirmar estados corretos após cada transição;
- testar o Laboratório com um comando conhecido;
- reduzir o fluxo diário ao atalho `Painel do Robô` e à interface Web local.

Critério de conclusão: mecanismos de parada, operação, diagnóstico e telemetria devem funcionar fisicamente sem bypass da Policy Layer e sem dependência normal de terminais separados.

## 3. Ativar o primeiro planner por IA

Depois da validação física e operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
