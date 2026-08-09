# NEXT

## 1. Concluir parada de emergência e ciclo operacional

O FAILSAFE explícito já foi aprovado no CI e revalidado fisicamente em dois cantos da tela. Em ambos os testes, `mover mouse 200 200` terminou como `failed` e a telemetria registrou `DesktopFailsafeTriggered` antes da entrada física.

O próximo passo é validar o mecanismo independente de parada de emergência e o ciclo normal de operação pelo Painel:

1. com Central e Robô ligados, ativar **Emergência** pelo Painel;
2. confirmar que o Robô é encerrado e que o estado persistente de emergência fica visível;
3. tentar iniciar o Robô enquanto a emergência estiver ativa e confirmar que o início permanece bloqueado;
4. liberar conscientemente a emergência pelo Painel;
5. ligar novamente o Robô e confirmar retorno ao estado **Ligado**;
6. validar também a sequência explícita **Parar Robô → Desligado → Ligar Robô → Ligado**;
7. testar o Laboratório com um comando conhecido;
8. confirmar que o fluxo diário pode ser feito pelo atalho `Painel do Robô` e pela interface Web local, sem dependência normal de terminais separados.

Critério de conclusão: parada de emergência, bloqueio persistente, liberação consciente, parada/início normal, diagnóstico e telemetria precisam funcionar fisicamente sem bypass da Policy Layer e sem dependência normal de terminais separados.

## 2. Ativar o primeiro planner por IA

Depois da validação física e operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
