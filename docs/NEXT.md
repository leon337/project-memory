# NEXT

## 1. Validar telemetria real de Central e Robô

A terceira revisão do Painel já foi carregada no computador alvo. Os **Controles de estado** foram validados fisicamente para Central, Robô e Emergência, e o log real do **Painel** já apareceu em **Logs reais da aplicação**.

A **Central que estava rodando fora do Painel foi encerrada manualmente com Ctrl+C**. O encerramento foi limpo, com `Shutting down`, `Application shutdown complete` e retorno ao prompt do terminal.

Próximos passos, em ordem:

1. confirmar no Painel que o controle da **Central** mudou de **Ligada fora do Painel** para **Desligada**;
2. iniciar a Central pelo próprio Painel com o código novo e confirmar que passa a estado gerenciado pelo Painel;
3. confirmar eventos reais no filtro **Central**;
4. reiniciar o **Robô** com o código novo e confirmar eventos reais no filtro **Robô**.

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
