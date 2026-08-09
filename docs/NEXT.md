# NEXT

## 1. Integrar Cerebras como primeiro planner por IA

A validação operacional do MVP 0.3 foi concluída no Linux real: FAILSAFE explícito, parada de emergência, ciclo normal parar/ligar Robô, telemetria e Laboratório já foram testados fisicamente.

A escolha vigente para a primeira integração de IA é **Cerebras** com o modelo **`gpt-oss-120b`**.

Próximos passos:

1. criar/obter a chave de API da Cerebras;
2. armazenar a chave somente no `.env`/variável de ambiente local;
3. conectar Cerebras ao contrato provider-agnostic existente em `src/context_anchor/planner.py`;
4. exigir saída compatível com `StructuredAction`;
5. manter toda saída passando pela Policy Layer;
6. manter `DeterministicPlanner` como fallback e para testes;
7. testar primeiro uma única ação simples em linguagem natural pelo mesmo caminho físico já validado.

Critério de conclusão: um pedido simples em linguagem natural deve ser interpretado por Cerebras, convertido em uma única ação estruturada conhecida, validado pela Policy Layer, executado pelo Robô e registrado na telemetria sem expor credenciais.

Uma pesquisa paralela está buscando outros provedores gratuitos com limites maiores. Se surgir uma opção claramente superior, a escolha pode ser revisada, mas isso deve gerar uma nova decisão explícita em `DECISIONS.md`; até lá, Cerebras + `gpt-oss-120b` é o alvo vigente.

## 2. Evoluir para planejamento multietapa orientado a objetivo

Depois que uma ação única por IA estiver estável, evoluir o planner para receber um objetivo e produzir/acompanhar múltiplas etapas com verificação de resultado entre elas.

O loop deve reutilizar as proteções existentes e nunca transformar a resposta do modelo em shell ou execução livre.

## 3. Preparar acesso remoto seguro e canais

Somente depois do planner por IA funcionar dentro das proteções atuais, preparar a camada de acesso remoto seguro antes de qualquer exposição à Internet.

Esse bloco deverá anteceder Telegram, WhatsApp e Instagram e incluir autenticação forte, TLS, pareamento/revogação, auditoria e confirmação para ações sensíveis.
