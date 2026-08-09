# NEXT

## 1. Executar baseline físico de linguagem natural

Testar frases com o mesmo objetivo, mas formulações progressivamente menos prescritivas, sem corrigir uma a uma durante o teste.

Registrar PASS/FAIL para cada caso e, quando falhar, classificar a causa em uma destas categorias:

- interpretação de intenção;
- resolução de aplicativo/capacidade;
- contexto entre tarefas;
- percepção/observação;
- provider/quota;
- execução física.

O objetivo é medir onde o Robô exige sintaxe específica antes de alterar a arquitetura.

## 2. Implementar camada geral de interpretação + contexto operacional

Depois do baseline, introduzir uma camada que transforme linguagem natural variada em intenção/capacidades sem depender de `regex` por frase.

Ela deve incluir:

- normalização de sinônimos e entidades;
- resolução geral de aplicativos/capacidades disponíveis;
- contexto operacional curto entre tarefas (`agora`, `nesse navegador`, `nesse site`, `depois`);
- preservação dos caminhos determinísticos atuais como fast path, não como linguagem obrigatória.

Critério de conclusão: pedidos semanticamente equivalentes devem produzir o mesmo objetivo operacional sem exigir que o usuário especifique navegador, URL ou aplicativo quando isso puder ser inferido.

## 3. Evoluir percepção + replanejamento para primeiro objetivo realmente autônomo

Depois da interpretação/contexto, ampliar observação de browser/desktop e testar um objetivo que exija:

```text
objetivo
→ observar
→ decidir
→ agir
→ verificar
→ replanejar se necessário
→ concluir
```

Priorizar observações estruturadas, como URL/título/conteúdo de página e janela ativa, antes de depender somente de visão por screenshot.

Garantir ao menos um provider de raciocínio disponível no router para esse teste.
