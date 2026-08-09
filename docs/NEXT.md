# NEXT

## 1. Revalidar fisicamente navegador + site sem provider

Atualizar a cópia local, reiniciar o Robô e enviar exatamente:

`Abra o navegador e acesse o site globo.com`

Critério de conclusão:

- o navegador estruturado abre;
- `https://globo.com` é carregado;
- task termina `succeeded`;
- o pedido é resolvido pelo caminho determinístico local;
- nenhum provider externo é necessário para essa tarefa.

## 2. Validar navegador específico + site

Enviar:

`Abra o navegador brave e acesse globo.com`

Critério de conclusão:

- não vira uma URL inválida;
- não chama provider externo;
- resolve Brave localmente com `https://globo.com` como argumento;
- Brave abre no site solicitado;
- se Brave não estiver instalado, a falha é de resolução/execução, não de allowlist.

## 3. Preparar e testar primeiro objetivo condicional real

Depois que os testes de navegação passarem, garantir ao menos um provider disponível para raciocínio — preferencialmente ativando Cloudflare Workers AI com o `Account ID` ou após a quota do Gemini voltar — e então testar um objetivo do tipo observar → decidir → agir → observar novamente.
