# NEXT

## 1. Revalidar fisicamente Brave + Google + pesquisa sem provider

Atualizar a cópia local, reiniciar o Robô e enviar exatamente:

`Abra o navegador brave e acesse o site google.com e pesquise o significado do nome Josiel`

Critério de conclusão:

- Brave abre;
- a página de resultados do Google para `o significado do nome Josiel` é carregada;
- task termina `succeeded`;
- rota é determinística/local;
- nenhum provider externo é necessário.

## 2. Revalidar pesquisa simples sem provider

Enviar exatamente:

`agora pesquise sobre inteligencia artificial`

Critério de conclusão:

- uma busca web por `sobre inteligencia artificial` é aberta;
- task termina `succeeded`;
- nenhum provider externo é necessário.

Observação: neste estágio esse comando isolado usa a navegação estruturada. Ele ainda não garante reutilizar um Brave aberto em uma tarefa anterior. Se o comportamento esperado for continuidade no mesmo navegador, implementar persistência de contexto entre tarefas antes de considerar essa parte concluída.

## 3. Preparar e testar o primeiro objetivo condicional real

Depois das pesquisas locais passarem, garantir ao menos um provider disponível para raciocínio — preferencialmente ativando Cloudflare Workers AI com o `Account ID` ou após a quota do Gemini voltar — e testar um objetivo do tipo observar → decidir → agir → observar novamente.
