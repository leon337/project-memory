# PM-HOME-REVIEW-001 — Rafael — Engenharia de Software

## Entrada recebida
Arquitetura de Sofia, requisitos de UX/UI/A11y e findings técnicos revalidados.

## Trabalho executado
Decomposição da futura implementação em slices pequenos, testáveis e reversíveis. Nenhum código funcional foi alterado nesta fase.

## Finding revalidado: `exatamente:`
Em `goal_interpreter.py`, `_extract_written_text()` remove prefixos como `texto:` e editor, mas não normaliza o modificador `exatamente:`. A suíte `test_goal_interpreter.py` cobre `Olá mundo`, aspas e `texto:`, sem caso equivalente a `escreva exatamente: Validação real número 1`.

## Plano de engenharia futuro
### Slice 0 — baseline
- adicionar teste regressivo para `exatamente:`;
- provar FAIL antes da correção;
- corrigir parser sem hardcode da frase de teste;
- provar PASS e regressão completa.

### Slice 1 — contratos da Home
- definir DTOs/estados de telemetria;
- separar endpoints/serviços de conversa e execução;
- contratos de erro, `BLOCKED`, `FAILED`, `SUCCEEDED`.

### Slice 2 — Conversation Service
- contexto sanitizado de projeto;
- provider configurável;
- zero acesso a executores físicos;
- testes que provem ausência de criação de task.

### Slice 3 — V4.1 UI
- faixa compacta de status;
- controles laterais compactos;
- chat central;
- painel `Agente agora` progressivo;
- detalhes fora da Home.

### Slice 4 — hardening
- Host/Origin/CSRF/CORS conforme threat model;
- proteção específica das mutações de controle.

### Slice 5 — validação
- testes unitários/integrados/UI;
- acessibilidade;
- teste físico do Linux/X11;
- auditoria final.

## Riscos
- duplicar estado da task na UI;
- Conversation Service acidentalmente reutilizar `submit_task`;
- regressão no Emergency Stop;
- telemetria com placeholders parecer real;
- redesign reduzir capacidade de diagnóstico.

## Decisão
`PASS_WITH_CHANGES` — arquitetura é implementável; primeiro trabalho funcional futuro deve ser a regressão `exatamente:`.

## Handoff
**Rafael → Ricardo**

Entrega: plano incremental e pontos de risco.
Próxima ação: modelar ameaças e requisitos de hardening das novas fronteiras.
Critério de conclusão: controles de segurança proporcionais ao localhost atual e à futura evolução.