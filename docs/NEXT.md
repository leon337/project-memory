# NEXT

## 1. Medir limites reais de SiliconFlow e Z.AI

A validação operacional do MVP 0.3 foi concluída no Linux real e a escolha anterior por Cerebras foi reaberta porque a pesquisa atualizada mostrou que o serviço não possui mais free tier recorrente.

Estado atual:

- conta e API key do **SiliconFlow** já foram criadas;
- conta e API key do **Z.AI** já foram criadas;
- nenhuma chave foi armazenada no Git ou enviada ao código do projeto;
- nenhum dos dois provedores está integrado ao Robô ainda.

Próximas verificações manuais:

1. no SiliconFlow, abrir **Higher Limits** e identificar limites atuais por conta/modelo; verificar também **Payments** apenas para saldo/créditos, sem adicionar pagamento;
2. no Z.AI, abrir **Rate Limits** e registrar RPM/TPM/concurrency/quota dos modelos gratuitos/Flash disponíveis para a conta;
3. comparar esses números com Cloudflare Workers AI e Groq, usando a pesquisa de agosto de 2026 como referência;
4. não assumir que um modelo é gratuito apenas porque aparece no catálogo — confirmar preço zero e natureza recorrente do plano.

Critério de conclusão: obter dados suficientes para dizer, sem suposição, quais candidatos oferecem gratuidade recorrente e qual volume real de uso está disponível para um planner iterativo.

## 2. Escolher o primeiro provedor de IA

Depois das medições, escolher explicitamente o primeiro provedor/modelo considerando em conjunto:

- gratuidade recorrente;
- RPM e TPM;
- RPD/TPD ou budget diário equivalente;
- Structured Outputs / JSON Schema;
- function/tool calling;
- reasoning;
- latência;
- estabilidade do free tier.

A decisão escolhida deverá ser registrada em `DECISIONS.md` antes da integração.

## 3. Integrar o provedor escolhido ao planner

Conectar o provedor vencedor ao contrato provider-agnostic em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes;
- primeiro teste usa uma única ação simples em linguagem natural pelo mesmo caminho físico já validado.