# PM-HOME-REVIEW-001 — Leonardo — Revalidação de Produto

## Entrada recebida
V1–V4 fornecidas por LEANDRO, V4 aceita como candidata para refinamento, baseline técnico reconciliado e proibição de alterar código funcional nesta fase.

## Trabalho executado
Reavaliação do papel da Home como produto, distinguindo operação cotidiana, transparência e superfície técnica.

## Evidências visuais
- **V1:** alta densidade operacional; fila, logs e atividade competem com o chat.
- **V2:** melhor separação de controles e painel `Agente agora`, porém ainda ocupa muito espaço com controles permanentes.
- **V3:** excelente foco conversacional, mas reduz demais a transparência operacional e não mostra `Agente agora`.
- **V4:** melhor equilíbrio: chat central, status superior compacto, navegação lateral e painel `Agente agora`.

## Requisitos de produto
1. A Home é a superfície principal para **conversar e delegar objetivos**, não um cockpit técnico.
2. O usuário deve saber imediatamente se Central, Robô, Desktop/Sistema, IA e Emergência estão operacionais.
3. Ação de conversa e ação que gera execução física precisam ser distinguíveis.
4. Fila, logs brutos, diagnóstico e histórico ficam disponíveis, mas fora do foco principal.
5. Resultado de tarefa deve comunicar **prova de conclusão**, não apenas sucesso técnico.
6. A Home precisa revelar quando IA foi ou não utilizada, sem inventar provider/modelo.
7. A interface deve responder à pergunta do usuário: “o robô realmente entendeu, fez e verificou?”

## Direção recomendada
Manter **V4 como base** e refiná-la para uma Home V4.1 final, incorporando:
- espaço conversacional da V3;
- clareza de `Agente agora` da V2;
- profundidade operacional da V1 apenas por navegação secundária;
- controles de estado compactos na primeira coluna.

## Decisão
`PASS`.

## Handoff
**Leonardo → Evelyn**

Entrega: requisitos de produto e direção V4 refinada.
Próxima ação: transformar esses requisitos em jornada e hierarquia de experiência.
Critério de conclusão: fluxo de experiência sem ambiguidade entre conversar, executar, acompanhar e investigar.