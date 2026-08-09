# NEXT

## 1. Concluir a validação do novo dark mode do Painel

A primeira revisão visual já está implementada no `main`, foi puxada para o computador alvo e a **Visão geral** já carregou corretamente pelo atalho do desktop.

Próximos passos, em ordem:

1. abrir **Configurações** e verificar se todos os cartões, botões, textos e diagnóstico continuam legíveis no tema escuro;
2. abrir **Laboratório** e verificar campos, botões, explicações e contraste;
3. confirmar com o usuário se o novo tema está confortável para uso prolongado ou se precisa de ajustes adicionais.

Critério de conclusão: o usuário deve considerar o novo tema confortável para uso prolongado e nenhum controle funcional pode ter sido prejudicado pela mudança visual.

## 2. Concluir segurança e operação física

Depois da validação visual, retomar os testes em passos pequenos:

- validar o `FAILSAFE` físico;
- validar a parada de emergência real pelo Painel e a liberação consciente do bloqueio;
- ligar, parar e reiniciar Central e Robô pelo Painel;
- confirmar estados corretos após cada transição;
- testar o Laboratório com um comando conhecido, confirmando explicação sem execução automática de shell;
- reduzir o fluxo diário ao atalho `Painel do Robô` e à interface Web local.

Critério de conclusão: mecanismos de parada, operação e diagnóstico devem funcionar fisicamente sem bypass da Policy Layer e sem dependência normal de terminais separados.

## 3. Ativar o primeiro planner por IA

Depois da validação física e operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
