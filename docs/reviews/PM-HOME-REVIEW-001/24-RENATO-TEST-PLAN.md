# PM-HOME-REVIEW-001 — Renato — Qualidade e Testes

## Entrada recebida
Requisitos funcionais, UX, acessibilidade, arquitetura, segurança, IA, avaliação e trace da missão.

## Trabalho executado
Transformação dos requisitos em protocolo de validação. Nenhum teste funcional novo é declarado executado nesta fase documental.

## Testes obrigatórios após autorização de implementação
### Parser / regressão
- `Abra um editor de texto e escreva exatamente: Validação real número 1` deve produzir texto-alvo exatamente `Validação real número 1`;
- o teste deve falhar no baseline atual e passar após a correção;
- regressão completa do Goal Interpreter permanece verde.

### Separação Conversar × Executar
- conversar com comando de ação: zero task criada, zero executor chamado;
- executar o mesmo comando: task criada e pipeline normal acionado;
- Enter/conversa não pode disparar execução por acidente.

### Goal Runtime / telemetria
- UI não mostra `SUCCEEDED` antes do GoalVerifier;
- `IA usada: NÃO` para fast path real sem provider;
- provider/modelo apenas quando registrados;
- `FAILED`/`BLOCKED` exibem critério pendente e causa sanitizada.

### Controles
- Central/Robô/Desktop refletem estado real antes e depois da mutação;
- Emergency Stop continua independente;
- limpar emergência exige o fluxo de proteção definido por Segurança.

### Segurança
- Host inválido rejeitado quando hardening implementado;
- Origin/CSRF cobrindo mutações browser-originated;
- CORS não amplia superfície;
- contexto conversacional não contém segredos.

### Acessibilidade
- teclado completo;
- foco visível;
- leitor de tela para estados/timeline;
- zoom 200%;
- reduced motion;
- estados não dependem só de cor.

### Teste físico Linux/X11
1. iniciar Painel/Central/Robô;
2. enviar `Executar objetivo` com o comando `exatamente:`;
3. observar editor real;
4. confirmar readback independente exato;
5. confirmar GoalVerifier `SUCCEEDED`;
6. verificar que o cartão final reproduz somente telemetria real.

## Critério global
Home pronta somente quando testes automatizados, integração UI, segurança, acessibilidade e prova física relevante passarem; mocks sozinhos não concluem o objetivo operacional.

## Decisão
`PASS_AS_PLAN`.

## Handoff
**Renato → Carmem**

Entrega: protocolo de aceite mensurável.
Próxima ação: consolidar a especificação final recomendada incorporando todos os requisitos e sem declarar implementação pronta.
Critério de conclusão: documento único, implementável e sem contradições com o baseline.