# NEXT

## 1. Validar Laboratório e operação diária sem terminal

O FAILSAFE explícito, a parada de emergência e o ciclo normal **Parar Robô → Desligado → Ligar Robô → Ligado** já foram validados fisicamente pelo Painel.

Agora falta validar o Laboratório e confirmar que o Painel é suficiente para a operação cotidiana do MVP 0.3:

1. abrir **Laboratório**;
2. testar um comando conhecido, começando por `git pull`;
3. confirmar que o Painel apenas explica a operação e não executa shell arbitrário;
4. voltar à Visão geral e confirmar que Central, Robô, diagnóstico, envio de tarefa e logs continuam acessíveis pela interface;
5. confirmar que o fluxo diário pode ser iniciado pelo atalho `Painel do Robô`, sem depender normalmente de terminais separados.

Critério de conclusão: o Laboratório deve explicar comandos conhecidos sem executar shell arbitrário, e o Painel deve ser suficiente para operação e diagnóstico cotidianos do MVP 0.3.

## 2. Ativar o primeiro planner por IA

Depois da validação operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

## 3. Preparar acesso remoto seguro e canais

Depois do primeiro planner por IA funcionar dentro das proteções atuais, preparar a camada de acesso remoto seguro antes de qualquer exposição à Internet.

Esse bloco deverá anteceder os adaptadores Telegram, WhatsApp e Instagram e incluir autenticação forte, TLS, pareamento/revogação, auditoria e confirmação para ações sensíveis.
