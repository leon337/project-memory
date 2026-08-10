# PM-HOME-REVIEW-001 — Tiago — IA e Machine Learning

## Entrada recebida
Arquitetura separando Conversation API de Task API, threat model e objetivo de permitir conversa real sobre o projeto.

## Trabalho executado
Definição do contrato de IA para conversa, interpretação e transparência.

## Papel da IA
### No modo Conversar
- responder perguntas sobre o projeto usando contexto explícito e sanitizado;
- explicar capacidades, estado operacional público e significado de falhas;
- preservar continuidade de conversa dentro de limites definidos;
- não criar task física.

### No modo Executar objetivo
- fast paths determinísticos continuam preferidos quando suficientes;
- IA pode ser usada para interpretação semântica, decomposição, ambiguidade e replanning;
- provider/modelo são detalhes de execução, não autoridade de conclusão;
- `GoalVerifier` continua sendo a única autoridade de `succeeded`.

## Contexto mínimo recomendado
- nome/identidade do projeto;
- objetivo e arquitetura resumida vigentes;
- decisões pertinentes;
- estado operacional não sensível;
- capability/task atual quando apropriado;
- proveniência/versão do contexto.

## Exclusões obrigatórias
- `.env` e credenciais;
- tokens/chaves;
- logs brutos desnecessários;
- dados pessoais não requeridos;
- cadeia privada de raciocínio.

## Transparência na Home
Exibir `IA usada: SIM/NÃO`. Quando SIM e houver dado real, mostrar provider/modelo. Quando NÃO, não preencher campos fictícios.

## Decisão
`PASS`.

## Handoff
**Tiago → Beatriz**

Entrega: contrato de comportamento da IA.
Próxima ação: definir testes independentes que provem contexto, não alucinação de estado e isolamento de execução.
Critério de conclusão: avaliação com critérios observáveis e falhas claramente classificadas.