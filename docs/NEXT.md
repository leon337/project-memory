# NEXT

## 1. Fechar configuração dos três provedores iniciais

A direção agora é multi-provider: **Z.AI/GLM + Cloudflare Workers AI + Google Gemini**.

Estado verificável:

- conta e API key do **Z.AI** já foram criadas;
- a tela real de Rate Limits da conta mostrou `GLM-4.7-Flash` com **concurrency 1**;
- a documentação/pesquisa confirma `GLM-4.7-Flash` com preço zero atual, reasoning, tools e structured output;
- token personalizado do **Cloudflare Workers AI** já foi criado com permissões **Read + Edit** e guardado localmente pelo usuário;
- o token Cloudflare está atualmente com escopo **Todas as contas**; antes da integração, preferir restringi-lo à conta específica e obter o `Account ID`;
- Google/Gemini já está disponível para o usuário, mas seus limites efetivos devem ser lidos no projeto do AI Studio;
- nenhuma credencial dos provedores foi adicionada ao Git;
- SiliconFlow permanece opcional até que um modelo gratuito atual e seus limites reais sejam comprovados.

Próximos passos:

1. restringir o token Cloudflare à conta específica, se possível, e obter o `Account ID`;
2. registrar os limites efetivos do projeto Gemini no AI Studio;
3. colocar as três credenciais somente no `.env` local quando os adaptadores forem implementados;
4. manter contadores locais para Z.AI, Cloudflare e Gemini onde o provedor não expuser telemetria completa de quota.

## 2. Implementar o roteador inteligente multi-provider

Criar uma camada de roteamento sobre o contrato provider-agnostic de `src/context_anchor/planner.py`.

O roteador deve escolher por capacidade, quota/budget, concorrência, latência, erros recentes e cooldown; não deve usar round-robin simples.

Papéis iniciais:

- GLM-4.7-Flash → reasoning/decisões complexas;
- Cloudflare Workers AI → decisões simples e frequentes/burst com modelo eficiente;
- Gemini → multimodalidade/visão e fallback complementar.

Toda resposta continua sendo convertida para `StructuredAction` e passando pela Policy Layer. `DeterministicPlanner` permanece como fallback e para testes.

## 3. Validar roteamento e fallback sem repetir ação física

Primeiro teste: uma única ação simples em linguagem natural deve ser planejada, validada e executada pelo mesmo caminho físico já aprovado.

Depois, simular indisponibilidade/`429` de um provedor e confirmar que o roteador seleciona outro provedor compatível.

Critério de segurança: fallback de IA não pode repetir automaticamente uma ação física já executada. O sistema deve verificar estado/resultado antes de qualquer nova execução.