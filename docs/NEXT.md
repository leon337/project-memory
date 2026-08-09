# NEXT

## 1. Revalidar fisicamente `abrir + escrever` sem provider

Atualizar a cópia local, reiniciar o Robô, fechar Xed/Gedit já aberto e enviar exatamente:

`Abra o editor de texto e escreva Olá mundo`

Critério de conclusão:

- editor abre;
- `Olá mundo` aparece exatamente, incluindo `á`;
- task termina `succeeded`;
- resultado contém 2 etapas: `open_app` e `type_text`;
- `planner_provider=deterministic` e `planner_route=local-sequence`;
- nenhum 429 de Gemini/Z.AI é necessário para essa tarefa.

## 2. Validar Brave pelo caminho determinístico local

Enviar:

`abrir o navegador brave`

Critério de conclusão:

- não vira URL;
- não chama provider externo;
- resolve `open_app(brave-browser)`;
- Brave instalado abre como aplicativo;
- se não existir executável compatível, a falha é de resolução/execução, não de allowlist.

## 3. Preparar e testar primeiro objetivo condicional real

Depois que os dois testes locais passarem, garantir ao menos um provider disponível para raciocínio — preferencialmente ativando Cloudflare Workers AI com o `Account ID` ou após a quota do Gemini voltar — e então testar um objetivo do tipo observar → decidir → agir → observar novamente.
