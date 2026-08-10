# PM-HOME-REVIEW-001 — Isabela — UI

## Entrada recebida
Fluxo UX de Laura, hierarquia de Evelyn e direção V4 refinada.

## Trabalho executado
Especificação visual da Home V4.1 sem transformar a revisão em implementação frontend.

## Estrutura visual recomendada
### Header
- marca/título à esquerda;
- sessão/ajuda/notificações à direita;
- sem texto técnico redundante.

### Faixa de estado
Uma única linha baixa com cinco estados reais:
`Central | Robô | Sistema/Desktop | IA | Emergência`.

Cada item combina ícone + texto + estado; cor é reforço, nunca única indicação.

### Coluna esquerda
- navegação textual com ícones;
- abaixo, controles compactos de Central, Robô, Desktop e Emergência;
- evitar cards altos e duplicação de estado.

### Centro
- chat ocupa a maior área;
- mensagens com largura confortável;
- cartão de execução aparece no próprio fluxo;
- composer com dois comandos: `Conversar` e `Executar objetivo`;
- atalhos como chips discretos abaixo do composer.

### Coluna direita
`Agente agora` com densidade moderada, se houver task/goal ativo. Pode recolher quando ocioso.

## Regras de estilo
- manter tema escuro e contraste forte;
- reduzir bordas e caixas aninhadas;
- usar verde apenas para estado realmente saudável/sucedido;
- vermelho reservado para perigo/falha/emergência;
- não usar placeholders como `GPT-4o`, IDs ou horários se não vierem da telemetria real;
- finalização deve priorizar `GoalVerifier` e readback/evidência.

## Decisão
`PASS_WITH_CHANGES` — V4 é visualmente a melhor base; a melhoria principal é compactar ainda mais a periferia e liberar área para o chat.

## Handoff
**Isabela → Marina**

Entrega: componentes e hierarquia visual.
Próxima ação: validar barreiras de acessibilidade e requisitos WCAG.
Critério de conclusão: especificação acessível sem depender de cor, mouse ou tamanho fixo.