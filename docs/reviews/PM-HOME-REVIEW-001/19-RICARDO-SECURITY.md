# PM-HOME-REVIEW-001 — Ricardo — Segurança

## Entrada recebida
Arquitetura de Sofia, plano de engenharia de Rafael e implementação atual do Painel.

## Trabalho executado
Threat model focado na fronteira browser-localhost e na separação entre conversa, execução e controles operacionais.

## Evidências atuais
`dashboard.py` expõe mutações para ligar/parar Central e Robô, alternar Desktop, acionar/limpar Emergência e submeter tasks. O controlador envia task para a Central com bearer token interno, mas a superfície browser do Painel não mostra no arquivo atual uma camada explícita equivalente de autenticação/Origin/CSRF/Trusted Host.

## Ameaças principais
1. Requisição browser-originated indevida contra endpoints locais mutáveis.
2. `clear emergency` acionado fora do fluxo esperado.
3. Conversa reutilizando por engano endpoint de execução.
4. Futuro acesso remoto expondo endpoints projetados para loopback.
5. Contexto de IA carregando segredo, `.env` ou log bruto.
6. UI exibindo dado sensível em evidência/erro sem redaction.

## Controles requeridos na futura implementação
- manter bind loopback por padrão;
- validar Host/Trusted Hosts;
- política explícita de Origin e proteção CSRF para mutações acionadas pelo browser;
- CORS restritiva/ausente quando desnecessária;
- separar tecnicamente Conversation API e Task API;
- tratar `clear emergency` como mutação sensível;
- manter segredos fora de payloads de contexto, logs e UI;
- não declarar “seguro para Internet” como consequência dessas medidas locais;
- criar nova camada de identidade/autorização se acesso remoto for introduzido futuramente.

## Avaliação
O finding não exige bloquear a revisão visual. Ele é requisito de implementação e teste antes de considerar a nova Home pronta.

## Decisão
`PASS_WITH_CHANGES`.

## Handoff
**Ricardo → Tiago**

Entrega: threat model e requisitos de hardening.
Próxima ação: definir o papel da IA e seu contrato com contexto/execução.
Critério de conclusão: IA útil à conversa e decomposição sem ganhar autoridade sobre efeitos físicos ou sucesso final.