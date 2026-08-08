# NEXT

## 1. Validar navegador, desktop e emergency stop no Linux real

Quando o usuário estiver no computador:

1. atualizar o repositório e reinstalar o pacote editável;
2. executar `context-anchor-doctor`;
3. instalar `xdotool`/`scrot` se o diagnóstico indicar ausência;
4. confirmar se a sessão é X11 ou Wayland;
5. manter `CONTEXT_ANCHOR_DESKTOP_ENABLED=false` e validar primeiro `abrir <site>` e `pesquisar <termo>`;
6. habilitar o desktop localmente;
7. testar `capturar tela`, `janela ativa`, movimento de mouse, clique, digitação, tecla e abertura de um aplicativo permitido;
8. testar `context-anchor-stop trigger` e confirmar que o agente encerra e não reinicia até `context-anchor-stop clear`.

Critério de conclusão: navegador, pelo menos uma ação de percepção, uma ação de mouse, uma ação de teclado, um aplicativo e o emergency stop devem funcionar no computador alvo sem bypass da Policy Layer.

## 2. Melhorar percepção e controle após o teste físico

Com base no resultado do diagnóstico real:

- corrigir incompatibilidades X11/Wayland encontradas;
- adicionar árvore de acessibilidade ou interface estruturada de janelas;
- melhorar verificação de clique/digitação em vez de assumir sucesso apenas porque a chamada do sistema retornou;
- preparar confirmação humana para ações sensíveis.

Critério de conclusão: o agente deve conseguir observar estado suficiente para verificar de forma confiável que uma ação de desktop produziu o efeito esperado.

## 3. Ativar o primeiro planner por IA

Depois da validação física, escolher um provedor e conectá-lo ao contrato já existente em `src/context_anchor/planner.py`.

Requisitos:

- saída obrigatoriamente compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída continua passando pela Policy Layer;
- `DeterministicPlanner` permanece disponível como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
