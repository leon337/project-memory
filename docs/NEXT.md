# NEXT

## 1. Validar telemetria real do Robô

A terceira revisão do Painel já está carregada no computador alvo. Os **Controles de estado** foram validados fisicamente para Central, Robô e Emergência.

Já foi confirmado no computador real:

- log real do **Painel**;
- transição da **Central** de ligada fora do Painel para desligada;
- início da Central pelo próprio Painel;
- Central passando a **Ligada e gerenciada pelo Painel**;
- eventos reais `[PAINEL]` e `[CENTRAL]` aparecendo em **Logs reais da aplicação**.

Próximos passos, em ordem:

1. usar **Reiniciar** no controle do **Robô local** para carregar o código novo;
2. confirmar que o Robô volta a **Ligado** após a reinicialização;
3. validar em **Logs reais da aplicação** eventos identificados como `[ROBÔ]`, preferencialmente usando o filtro **Robô**;
4. observar se o controle de estado acompanha corretamente a transição durante a reinicialização.

Critério de conclusão: Painel, Central e Robô devem produzir telemetria real identificada por origem, e os controles devem refletir corretamente as transições observadas.

## 2. Concluir segurança e operação física

Depois da validação da telemetria do Robô:

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
