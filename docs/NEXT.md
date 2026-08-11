# NEXT

## 1. Debater e planejar `PM-UNIVERSAL-OPERATOR-001` com o MCF

A direção estratégica já foi escolhida: evoluir o Robô para um **Operador Digital Autônomo Multimodal** capaz de transformar objetivos em linguagem natural em trabalho real no computador e em serviços digitais.

Antes de implementar código, o debate com o MCF deve fechar pelo menos:

- escopo da primeira entrega e critérios de aceitação;
- arquitetura e fronteiras entre Goal Runtime, capabilities e interfaces de execução;
- quando usar API/MCP, CLI/terminal, automação web estruturada ou mouse/teclado;
- tratamento de credenciais e sessões autenticadas;
- papel de voz bidirecional, contexto conversacional e ponte ChatGPT → Robô na sequência de fases;
- identidade durável, replay safety, percepção e verificação para novas ações físicas/externas;
- estratégia de testes automatizados e físicos.

O nome `PM-UNIVERSAL-OPERATOR-001 — Natural Language → Real Computer Work` é provisório até esse planejamento ser aprovado.

## 2. Converter o planejamento aprovado em contrato executável

Depois do debate, atualizar somente as decisões/arquitetura realmente aprovadas e transformar o resultado em escopo implementável: issue/missão, critérios de aceitação, capacidades, sequência de entrega, testes e evidências exigidas. Não iniciar implementação com pontos arquiteturais ainda em aberto.

## 3. Preservar as garantias já comprovadas

Qualquer nova capacidade deve manter Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente, EvidenceRecord e GoalVerifier como única autoridade de conclusão. Se uma capacidade precisar repetir legitimamente duas ações físicas idênticas na mesma task, deve introduzir identidade durável explícita em vez de usar contador implícito de retry/reclaim.