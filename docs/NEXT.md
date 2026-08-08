# NEXT

## 1. Validar percepção e controle do desktop no Linux real

A validação física do navegador foi concluída com sucesso para `abrir <site>` e `pesquisar <termo>`.

Próximo fluxo, em passos pequenos:

1. atualizar a instalação editável para disponibilizar os novos comandos `central`, `robo`, `parar-robo` e `diagnostico-robo`;
2. habilitar `CONTEXT_ANCHOR_DESKTOP_ENABLED=true` localmente e reiniciar somente o Robô com `robo`;
3. testar `capturar tela` e `janela ativa`, depois movimento de mouse, clique, digitação, tecla e abertura de um aplicativo permitido;
4. por fim testar `parar-robo trigger` e confirmar que o Robô encerra e não reinicia até `parar-robo clear`.

Critério de conclusão: pelo menos uma ação de percepção, uma ação de mouse, uma ação de teclado, um aplicativo e a parada de emergência devem funcionar no computador alvo sem bypass da Policy Layer.

## 2. Melhorar percepção e controle após o teste físico

Com base no resultado real:

- adicionar árvore de acessibilidade ou interface estruturada de janelas;
- melhorar verificação de clique/digitação em vez de assumir sucesso apenas porque a chamada do sistema retornou;
- preparar confirmação humana para ações sensíveis.

Critério de conclusão: o Robô deve conseguir observar estado suficiente para verificar de forma confiável que uma ação de desktop produziu o efeito esperado.

## 3. Ativar o primeiro planner por IA

Depois da validação física, escolher um provedor e conectá-lo ao contrato já existente em `src/context_anchor/planner.py`.

Requisitos:

- saída obrigatoriamente compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída continua passando pela Policy Layer;
- `DeterministicPlanner` permanece disponível como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
