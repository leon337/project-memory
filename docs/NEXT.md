# NEXT

## 1. Validar fisicamente o loop orientado a objetivo

Atualizar a cópia local, reiniciar o Robô e repetir exatamente:

`Abra o editor de texto e escreva Olá mundo`

Critério de conclusão:

- editor abre;
- foco permanece correto;
- `Olá mundo` é realmente digitado;
- o planner continua depois de `open_app`;
- uma decisão posterior retorna `finish`;
- a task só então termina `succeeded`;
- logs/resultados mostram mais de uma etapa no objetivo.

## 2. Validar fisicamente a política permissiva e o Brave

Testar:

`abrir o navegador brave`

Critério de conclusão:

- a frase não vira URL;
- o planner escolhe `open_app`;
- Brave é resolvido para um executável instalado e abre como aplicativo;
- se um aplicativo/comando não existir, a falha deve ser de resolução/execução (`FileNotFoundError` ou equivalente), não `PermissionError` de allowlist.

## 3. Depois das validações, testar objetivo condicional real

Executar um primeiro caso do tipo observar → decidir → agir → observar novamente, sem ainda depender de visão semântica avançada. Depois disso, retomar metadados de falha, Cloudflare Workers AI e quota manager.
