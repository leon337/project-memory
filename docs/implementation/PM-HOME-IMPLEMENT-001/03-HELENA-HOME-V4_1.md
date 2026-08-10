# PM-HOME-IMPLEMENT-001 — Helena — Engenharia Frontend

## agent
Helena — Engenharia Frontend.

## scope
Materializar a Home V4.1 sem alterar o Goal Runtime.

## implementation
Foi criada `src/context_anchor/dashboard_ui.py` e o HTML monolítico antigo saiu de `dashboard.py` para uma fronteira visual separada.

A Home implementa:
- faixa superior compacta: Central, Robô, Sistema, IA, Emergência;
- primeira coluna com controles pequenos de estado;
- navegação Home, Tarefas, Histórico, Diagnóstico e Configurações;
- chat como área dominante;
- dois controles distintos: `Conversar` e `Executar objetivo`;
- Enter associado à conversa por padrão;
- `Agente agora` na direita;
- resultado `Objetivo concluído` somente quando a task tem `succeeded + goal_completed=true + verified=true`;
- provider/modelo de conversa vindos da resposta real da Conversation API;
- `Agente agora` não usa task terminal antiga como se ainda estivesse executando;
- fila/logs/diagnóstico movidos para páginas secundárias;
- layout responsivo e `prefers-reduced-motion`.

## evidence
- `tests/test_dashboard_v4_1.py` define a fronteira de interação e a presença dos controles estruturais.
- `tests/test_dashboard_browser_v4_1.py` executa a Home em Chromium real de CI, exercitando conversa por Enter e execução somente pelo botão explícito.
- CI de integração anterior: run `31365499078` / run 298 = `SUCCESS`.
- O teste Chromium foi criado depois e passou por ciclo de recuperação documentado por Patrícia.

## accessibility_implementation
- foco visível via `:focus-visible`;
- `aria-live` em status, thread e toast;
- labels acessíveis para campos;
- switch com `role="switch"` e `aria-checked`;
- texto acompanha cor nos estados;
- responsive layout;
- reduced motion.

## decision
`PASS_WITH_CHANGES`

Validação visual/física no Linux do operador ainda pertence ao gate físico da missão.

## artifact
`src/context_anchor/dashboard_ui.py`, testes de UI e este registro.

## handoff
Helena → Ricardo/Tiago.

Entrega: superfície V4.1 funcional e semanticamente separada.
Próxima ação: validar fronteiras de segurança e ligar o modo Conversar a IA real sem permitir task física.
Critério: conversa isolada, mutações protegidas e telemetria não fabricada.
