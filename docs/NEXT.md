# NEXT

## 1. Validar o Painel do Robô no Linux real

O primeiro Painel do Robô já está implementado e passou no CI.

Próximo teste, em passos pequenos:

1. atualizar o computador com `git pull` e `pip install -e .`;
2. parar uma vez a Central antiga que já estava rodando antes do registro de PID novo;
3. iniciar `painel-robo` e abrir `http://127.0.0.1:8765`;
4. confirmar visualmente os estados de Central, Robô, Desktop e emergência;
5. ligar/reiniciar Central e Robô pelos botões do Painel;
6. executar o diagnóstico pelo Painel;
7. testar o Laboratório com `git pull` e confirmar que a explicação aparece sem execução automática de shell.

Critério de conclusão: o usuário deve conseguir administrar o ciclo básico pelo Painel sem precisar manter três terminais para Central, Robô e configuração.

## 2. Validar percepção e controle do desktop pelo Painel

Com o Painel validado, continuar o teste físico no Linux/X11:

- `capturar tela`;
- `janela ativa`;
- movimento e clique do mouse;
- digitação e teclas;
- abertura de aplicativo permitido;
- parada de emergência real pelo Painel;
- confirmar comportamento do `FAILSAFE`.

Critério de conclusão: pelo menos uma ação de percepção, uma ação de mouse, uma ação de teclado, um aplicativo e a parada de emergência devem funcionar sem bypass da Policy Layer.

## 3. Ativar o primeiro planner por IA

Depois da validação física, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
