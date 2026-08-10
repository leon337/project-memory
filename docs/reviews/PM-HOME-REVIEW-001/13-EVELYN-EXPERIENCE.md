# PM-HOME-REVIEW-001 — Evelyn — Gestão de Design e Experiência

## Entrada recebida
Requisitos de produto de Leonardo e V4 como base de refinamento.

## Trabalho executado
Organização da experiência em quatro momentos do operador: entender estado, conversar, delegar objetivo e acompanhar/verificar.

## Jornada recomendada
```text
ABRIR HOME
→ entender estado em poucos segundos
→ CONVERSAR ou EXECUTAR OBJETIVO
→ se conversar: resposta sem criar task física
→ se executar: ENFILEIRADO → INTERPRETANDO → PLANEJANDO → EXECUTANDO → VERIFICANDO
→ SUCCEEDED | FAILED | BLOCKED
→ detalhes somente quando solicitados
```

## Hierarquia
1. Chat/objetivo atual.
2. Estado do Robô e etapa atual.
3. Estado global compacto.
4. Controles de estado essenciais.
5. Atalhos e detalhes técnicos.

## Achados
- A V3 acerta no foco, mas esconde contexto operacional demais.
- A V1 revela demais e transforma a Home em dashboard técnico.
- A V4 está mais próxima do modelo mental correto: conversa no centro, operação contextual na periferia.
- A Home deve usar **progressive disclosure**: resumo primeiro, evidência detalhada sob demanda.

## Decisão
`PASS_WITH_CHANGES` — preservar V4, reduzir densidade periférica e tornar os estados do ciclo explícitos.

## Handoff
**Evelyn → Laura**

Entrega: jornada e hierarquia de experiência.
Próxima ação: detalhar fluxo de interação, navegação e prevenção de erro.
Critério de conclusão: UX operacional coerente em todos os estados principais.