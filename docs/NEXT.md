# NEXT

## 1. Concluir o ciclo operacional normal pelo Painel

O FAILSAFE explícito e a parada de emergência já foram validados fisicamente.

A parada de emergência foi testada em dois ciclos reais pelo Painel:

- ativação colocou o estado em **ATIVA**;
- o Robô foi encerrado e apareceu como **DESLIGADO**;
- início e reinício ficaram bloqueados enquanto a emergência estava ativa;
- a liberação devolveu o estado para **NORMAL** sem reiniciar automaticamente;
- o Robô voltou a **LIGADO** somente depois de ação humana explícita;
- os logs registraram ativação, liberação, solicitação de início, novo PID e inicialização do Robô.

Agora falta validar o caminho normal, sem usar a emergência:

1. com o Robô ligado, clicar em **Parar Robô**;
2. confirmar estado **DESLIGADO** e disponibilidade da ação **Ligar Robô**;
3. clicar em **Ligar Robô**;
4. confirmar retorno para **LIGADO** e novo evento de inicialização nos logs.

Critério de conclusão: **Parar Robô → Desligado → Ligar Robô → Ligado** deve funcionar integralmente pelo Painel, sem terminal e sem acionar a emergência.

## 2. Validar Laboratório e operação diária sem terminal

Depois do ciclo normal:

1. abrir **Laboratório**;
2. testar um comando conhecido, começando por `git pull`;
3. confirmar que o Painel apenas explica a operação e não executa shell arbitrário;
4. confirmar que o fluxo diário — abrir pelo atalho, ligar/parar Central e Robô, diagnóstico, envio de tarefa e consulta de logs — pode ser feito sem dependência normal de terminais separados.

Critério de conclusão: o Painel deve ser suficiente para operação e diagnóstico cotidianos do MVP 0.3.

## 3. Ativar o primeiro planner por IA

Depois da validação operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
