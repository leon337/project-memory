# NEXT

## 1. Corrigir e revalidar o FAILSAFE físico

A primeira validação física do FAILSAFE falhou: com o ponteiro no canto superior esquerdo, a tarefa `mover mouse 200 200` foi executada e terminou como `succeeded`.

O backend atualmente ativa `pyautogui.FAILSAFE = True`, mas isso não foi suficiente no computador alvo.

Próximos passos:

1. adicionar no backend de desktop uma proteção explícita própria antes de ações físicas, tratando uma pequena zona dos cantos da tela como área de parada;
2. cobrir a proteção com testes automatizados;
3. baixar/reiniciar o Robô;
4. repetir fisicamente `mover mouse 200 200` com o ponteiro na zona de segurança.

Critério de conclusão: a ação deve ser recusada antes do movimento, a tarefa deve terminar como `failed` e a telemetria deve registrar a interrupção de segurança.

## 2. Concluir parada de emergência e ciclo operacional

Depois do FAILSAFE corrigido e aprovado:

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
