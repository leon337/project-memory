# NEXT

## 1. Validar Controles de estado e logs reais

A terceira revisão do Painel já está no `main` e passou no CI.

Próximos passos, em ordem:

1. executar `git pull` no computador alvo e reiniciar apenas o **Painel do Robô**;
2. confirmar que Central, Robô e Emergência mostram estado real e que a ação oferecida muda conforme esse estado;
3. se a Central ainda estiver iniciada fora do Painel, confirmar que aparece como **ligada fora do Painel**;
4. reiniciar Central e Robô com o código novo e validar em **Logs reais da aplicação** eventos de Painel, Central e Robô, usando os filtros por componente.

Critério de conclusão: nenhum controle pode parecer ligado/desligado de forma ambígua, e os logs exibidos devem corresponder a eventos realmente produzidos pelos componentes.

## 2. Concluir segurança e operação física

Depois da validação dos controles e telemetria:

- validar o `FAILSAFE` físico;
- validar a parada de emergência real pelo Painel e a liberação consciente do bloqueio;
- completar o ciclo ligar/parar/reiniciar Central e Robô pelo Painel;
- confirmar estados corretos após cada transição;
- testar o Laboratório com um comando conhecido;
- reduzir o fluxo diário ao atalho `Painel do Robô` e à interface Web local.

Critério de conclusão: mecanismos de parada, operação, diagnóstico e telemetria devem funcionar fisicamente sem bypass da Policy Layer e sem dependência normal de terminais separados.

## 3. Ativar o primeiro planner por IA

Depois da validação física e operacional, escolher um provedor e conectá-lo ao contrato existente em `src/context_anchor/planner.py`.

Requisitos:

- saída compatível com `StructuredAction`;
- nenhuma ação de shell;
- nenhuma credencial enviada ao modelo;
- toda saída passa pela Policy Layer;
- `DeterministicPlanner` permanece como fallback e para testes.

Depois desse marco, o próximo bloco será acesso remoto seguro e adaptadores Telegram/WhatsApp/Instagram.
