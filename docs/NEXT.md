# NEXT

## 1. Validar o teste vertical em um desktop Linux real

Executar o Control Plane e o agente local no computador alvo e confirmar o ciclo completo:

```text
painel Web
→ criar tarefa
→ agente reivindica
→ Playwright abre/pesquisa no navegador
→ agente verifica o resultado
→ painel recebe succeeded/failed
```

Critério de conclusão: pelo menos um comando `abrir <site>` e um comando `pesquisar <termo>` devem concluir corretamente fora do ambiente de CI.

## 2. Adicionar o primeiro slice de percepção e controle do desktop

Depois da validação do navegador, implementar ações tipadas para:

- capturar o estado visual da tela;
- identificar a janela ativa;
- mover/clicar o mouse;
- digitar texto;
- abrir um aplicativo explicitamente permitido.

Todas as novas ações devem passar pela Policy Layer. Também deve ser criado um emergency stop local independente do agente.

## 3. Integrar um planner por IA com saída estruturada

Somente depois dos dois itens anteriores, adicionar uma interface de provedor de modelo que transforme objetivos em ações tipadas já suportadas pelo executor.

O LLM não poderá gerar shell arbitrário nem receber credenciais. O planner determinístico atual deverá permanecer disponível para testes e fallback.
