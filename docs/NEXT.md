# NEXT

## 1. Ativar o primeiro planner por IA

A validação operacional do MVP 0.3 foi concluída no Linux real: FAILSAFE explícito, parada de emergência, ciclo normal parar/ligar Robô, telemetria e Laboratório já foram testados fisicamente.

O próximo marco é escolher e conectar um provedor de IA ao contrato existente em `src/context_anchor/planner.py`.

Requisitos obrigatórios:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída continua passando pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes;
- erros do provedor não podem derrubar o Robô nem remover as proteções físicas já validadas.

Primeira entrega esperada: um comando simples em linguagem natural deve ser convertido pela IA em uma única ação estruturada conhecida, validada pela Policy Layer e executada pelo mesmo caminho físico já aprovado.

## 2. Evoluir para planejamento multietapa orientado a objetivo

Depois que uma ação única por IA estiver estável, evoluir o planner para receber um objetivo e produzir/acompanhar múltiplas etapas com verificação de resultado entre elas.

O loop deve reutilizar as proteções existentes e nunca transformar a resposta do modelo em shell ou execução livre.

## 3. Preparar acesso remoto seguro e canais

Somente depois do planner por IA funcionar dentro das proteções atuais, preparar a camada de acesso remoto seguro antes de qualquer exposição à Internet.

Esse bloco deverá anteceder Telegram, WhatsApp e Instagram e incluir autenticação forte, TLS, pareamento/revogação, auditoria e confirmação para ações sensíveis.
