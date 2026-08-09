# NEXT

## 1. Implementar interpretação geral + decomposição de objetivo

O baseline físico foi concluído. Não adicionar novos `regex` por frase como estratégia principal.

Introduzir uma camada explícita que transforme linguagem natural em:

- intenção principal;
- entidades relevantes;
- capacidades necessárias;
- subobjetivos ordenados;
- critérios de conclusão do objetivo inteiro.

Ela deve resolver semanticamente casos como:

- `Quero fazer uma anotação. Abra alguma coisa onde eu possa escrever` → capacidade de edição;
- `Abra o Visual Studio Code` e `Abra o VS Code` → mesma entidade/aplicativo;
- `Preciso fazer algumas contas` → capacidade de calculadora disponível;
- `Quero saber o significado do nome Josiel` → objetivo informacional que pode exigir pesquisa;
- pedidos compostos com `e depois`, sem transformar a frase inteira em uma única consulta de busca.

Critério de conclusão: pedidos semanticamente equivalentes geram a mesma representação operacional e um pedido composto não pode perder subobjetivos silenciosamente.

## 2. Adicionar estado/evidência de objetivo e eliminar falso `succeeded`

Representar por task:

- objetivo original;
- subobjetivos pendentes/concluídos;
- evidências observadas por etapa;
- estado operacional relevante;
- motivo explícito de conclusão.

Alterar o encerramento para que `succeeded` só seja emitido quando todos os critérios necessários do objetivo estiverem comprovados.

Regressão obrigatória baseada no FAIL físico:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

Não pode ser considerado sucesso apenas porque uma busca foi aberta. O sistema precisa, no mínimo, pesquisar, observar/obter o primeiro resultado, abrir o editor, escrever o título e verificar a escrita antes de concluir.

## 3. Evoluir percepção + contexto operacional e validar primeiro objetivo condicional

Adicionar observações estruturadas suficientes para o loop autônomo, priorizando:

- URL atual;
- título e texto/DOM útil da página;
- janela/aplicativo ativo;
- resultado de abertura/escrita;
- contexto curto entre tasks (`agora`, `lá`, `nesse navegador`, `nesse site`, `depois`).

Depois validar fisicamente um objetivo condicional real:

```text
Verifique uma condição observável.
Se verdadeira, execute A.
Se falsa, execute B.
```

Garantir ao menos um provider de raciocínio disponível no router durante esse teste, sem depender dele para fast paths determinísticos já conhecidos.
