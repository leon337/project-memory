# NEXT

## 1. Revalidar fisicamente o FAILSAFE explícito

A primeira validação física do FAILSAFE nativo do PyAutoGUI falhou: com o ponteiro no canto superior esquerdo, a tarefa `mover mouse 200 200` foi executada e terminou como `succeeded`.

A correção já está implementada no `main`:

- `PyAutoGuiDesktopBackend` mantém `pyautogui.FAILSAFE = True` como defesa adicional;
- antes de mover, clicar, digitar ou pressionar tecla, o backend verifica a posição atual do ponteiro;
- uma zona de 20 pixels nos quatro cantos funciona como FAILSAFE explícito do Robô;
- quando o ponteiro está nessa zona, `DesktopFailsafeTriggered` é levantado antes de qualquer entrada física;
- testes automatizados cobrem os quatro cantos, bloqueio de mouse/teclado e execução normal fora da zona;
- CI do commit `4f398f4f745fbd996db13c710601fa83b3da5c37` concluiu com `success`.

Próximos passos no computador alvo:

1. sincronizar o `main` local com o GitHub;
2. reiniciar o Robô pelo Painel para carregar o código novo;
3. colocar o ponteiro no canto superior esquerdo;
4. enviar `mover mouse 200 200`;
5. verificar no Painel que a tarefa terminou como `failed` e que o log do Robô registra `DesktopFailsafeTriggered`.

Critério de conclusão: o ponteiro não deve sair do canto por ação do Robô, a tarefa deve terminar como `failed` e a telemetria deve registrar a interrupção de segurança.

## 2. Concluir parada de emergência e ciclo operacional

Depois do FAILSAFE corrigido e aprovado fisicamente:

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
