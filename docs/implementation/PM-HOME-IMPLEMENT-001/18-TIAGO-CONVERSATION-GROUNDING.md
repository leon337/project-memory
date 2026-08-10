# PM-HOME-IMPLEMENT-001 — Tiago — Grounding da Identidade do Projeto

## agent
Tiago — IA e Machine Learning.

## input
Finding físico `CONVERSATION-IDENTITY-001`: em uma execução real o provider respondeu `Robô Operador — MVP 0.3` à pergunta canônica `Em qual projeto você está?`, embora a identidade do repositório seja `project-memory`.

## action
A fronteira conversacional foi endurecida sem criar resposta fictícia local:

- `project-memory` passou a ser fato canônico explícito;
- a identidade canônica é reafirmada depois do contexto documental, para que títulos encontrados em README/STATUS não tenham precedência acidental;
- perguntas que explicitamente pedem a identidade do projeto validam a resposta do provider;
- se o primeiro provider responder algo incompatível com o fato canônico, a resposta é recusada e o fallback normal continua para o próximo provider;
- a IA ainda precisa fornecer a resposta; o serviço apenas rejeita contradição com um fato conhecido do próprio projeto.

## evidence
- RED: CI run 343 mostrou que a fronteira anterior aceitava `Robô Operador — MVP 0.3` sem fallback;
- implementação: `src/context_anchor/conversation.py`;
- regressões: `tests/test_physical_flakiness.py`;
- um teste legado de fingerprint precisou alinhar seu fake provider ao novo contrato de identidade; a alteração é somente no fixture do teste e não relaxa a validação.

## decision
`PASS_PENDING_CI`

## handoff
Tiago → Renato/Beatriz.

Próxima ação: confirmar suíte integral verde e depois repetir o validador físico no candidato atualizado, pois a Conversation API mudou depois do primeiro `PASS_GATE` físico.
Critério: zero regressão automatizada e novo PASS da conversa real no ambiente operacional.