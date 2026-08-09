# NEXT

## 1. Validar FAILSAFE físico

Painel, Central e Robô já produziram telemetria real identificada por origem no computador alvo. Os **Controles de estado** também acompanharam as principais transições observadas, incluindo a Central passando de externa para desligada e depois para gerenciada pelo Painel, além do reinício real do Robô pelo próprio Painel.

Próximo passo:

1. validar fisicamente o `FAILSAFE` do PyAutoGUI em uma ação controlada, confirmando que o mecanismo de segurança interrompe a ação quando o ponteiro é levado ao canto configurado.

Critério de conclusão: o FAILSAFE deve interromper a ação de desktop de forma observável e sem deixar o Robô em estado enganoso.

## 2. Concluir parada de emergência e ciclo operacional

Depois do FAILSAFE:

- validar a parada de emergência real pelo Painel;
- confirmar que o Robô é encerrado e o bloqueio persistente fica visível;
- liberar conscientemente a emergência;
- validar a sequência **Parar Robô → Desligado → Ligar Robô → Ligado**;
- testar o Laboratório com um comando conhecido;
- confirmar que o fluxo diário pode ser feito pelo atalho `Painel do Robô` e pela interface Web local, sem dependência normal de terminais separados.

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
