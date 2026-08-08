# NEXT

## 1. Implementar o primeiro Painel do Robô

Criar um processo local independente da Central e do Robô para reduzir dependência de múltiplos terminais durante desenvolvimento e operação.

Primeiro slice do painel:

- mostrar se Central e Robô estão ligados;
- botões para ligar, desligar e reiniciar Central e Robô;
- mostrar e alterar `DESKTOP_ENABLED` por controle visual;
- mostrar estado da parada de emergência;
- botão de diagnóstico;
- logs básicos separados de Central e Robô;
- área de comandos de manutenção controlados com explicação antes da execução;
- modo de aprendizado mostrando o que cada botão/comando faz e o resultado esperado.

Critério de conclusão: o usuário deve conseguir iniciar e parar Central/Robô, habilitar o desktop, executar diagnóstico e entender visualmente o estado do sistema sem precisar administrar três terminais manualmente.

## 2. Validar percepção e controle do desktop pelo Painel do Robô

Com o painel operacional, continuar a validação física já iniciada no Linux/X11.

Testar em sequência:

- `capturar tela` e `janela ativa`;
- movimento e clique do mouse;
- digitação e teclas;
- abertura de aplicativo permitido;
- parada de emergência real.

Critério de conclusão: pelo menos uma ação de percepção, uma ação de mouse, uma ação de teclado, um aplicativo e a parada de emergência devem funcionar no computador alvo sem bypass da Policy Layer.

## 3. Ativar o primeiro planner por IA

Depois da validação física, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída obrigatoriamente compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída continua passando pela Policy Layer;
- `DeterministicPlanner` permanece disponível como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
