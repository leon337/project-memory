# PM-HOME-IMPLEMENT-001 — Tiago — IA Conversacional

## agent
Tiago — IA e Machine Learning.

## scope
Criar conversa real com IA para provar que o Painel conhece o projeto, sem conceder à conversa autoridade de execução ou conclusão.

## implementation
Foi criado `src/context_anchor/conversation.py` com `ProjectConversationService`.

### Contexto permitido
Somente arquivos documentais explicitamente selecionados:
- `README.md`;
- `docs/STATUS.md`;
- `docs/ARCHITECTURE.md`;
- `docs/DECISIONS.md`;
- `docs/NEXT.md`.

`.env` não participa do contexto.

Todo contexto e mensagem do usuário passam por `redact_text()` antes de provider. A versão do contexto é um prefixo SHA-256 estável do conteúdo sanitizado.

### Provider routing
O modo Conversar usa fallback compatível com a ordem operacional vigente:
1. Cloudflare Workers AI;
2. Z.AI;
3. Gemini.

A resposta informa apenas o provider/modelo efetivamente usado naquele request.

### Isolamento
O system prompt determina explicitamente que a rota de conversa:
- não executa ações físicas;
- não cria task;
- não usa mouse/teclado/navegador/subprocesso;
- não anuncia execução fictícia;
- não substitui GoalVerifier.

No código, `ProjectConversationService` não recebe `DashboardController`, `TaskStore`, executor ou Policy Layer; a rota `/api/conversation` chama apenas o backend conversacional.

## evidence
- `test_conversation_endpoint_never_submits_a_task`;
- `tests/test_conversation.py` valida sanitização de segredo do contexto, exclusão de `.env`, sanitização de mensagem e fingerprint estável;
- RED de privacidade: run `31365593830` / run 299 = `FAILURE`;
- GREEN após correção: run `31365721132` / run 300 = `SUCCESS`;
- teste Chromium verifica provider/modelo reais fornecidos pela Conversation API usando backend controlado de teste.

## decision
`PASS_WITH_CHANGES`

A prova com provider real configurado permanece no script físico/local, porque CI não recebe credenciais de produção do operador.

## artifact
`conversation.py`, testes de conversa e este documento.

## handoff
Tiago → Beatriz/Júlia.

Entrega: serviço de conversa isolado e sanitizado.
Próxima ação: avaliar comportamento e governança do novo caminho de IA.
Critério: zero task em Conversar, contexto de projeto correto e nenhum ganho de autoridade operacional pela IA.
