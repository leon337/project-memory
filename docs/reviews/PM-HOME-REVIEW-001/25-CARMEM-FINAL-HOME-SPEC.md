# PM-HOME-REVIEW-001 — Carmem — Especificação Final Recomendada da Home

**Status:** especificação recomendada da fase; não representa implementação funcional.

## 1. Decisão de design
Usar **V4 como base** e refiná-la como **Home V4.1**.

A recomendação mantém o equilíbrio da V4 e incorpora seletivamente:
- V3: maior respiro e foco conversacional;
- V2: clareza do painel `Agente agora`;
- V1: profundidade de fila/logs somente em páginas secundárias.

## 2. Objetivo da Home
Permitir que o operador:
1. entenda rapidamente se o Robô está pronto;
2. converse com a IA sobre o projeto;
3. delegue objetivos explicitamente;
4. acompanhe a execução real;
5. verifique se o resultado foi comprovado;
6. aprofunde detalhes apenas quando necessário.

## 3. Wireframe recomendado
```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Painel do Robô                         ajuda/notificações     sessão      │
├───────────────┬──────────────────────────────────────┬───────────────────┤
│ Central ONLINE│ Central | Robô | Sistema | IA | Emergência             │
│ Robô   ONLINE ├──────────────────────────────────────┤ Agente agora      │
│ Desktop ATIVO │                                      │ status            │
│ Emerg. NORMAL │ Conversar com a IA                   │ etapa atual       │
│───────────────│                                      │ intent/capability │
│ Home          │ mensagens / objetivo / evidência     │ provider/modelo*  │
│ Tarefas       │                                      │ GoalVerifier      │
│ Histórico     │ [ Digite sua mensagem...          ]  │ task/goal id      │
│ Diagnóstico   │ [ Conversar ] [ Executar objetivo ]  │ duração           │
│ Configurações │ atalhos contextuais                  │                   │
└───────────────┴──────────────────────────────────────┴───────────────────┘
* somente quando realmente usado/observado
```

## 4. Faixa superior de estado
Linha horizontal compacta, sem grandes cards:
- Central;
- Robô local;
- Sistema/Desktop;
- IA;
- Emergência.

Estado deve vir de telemetria real e combinar texto + ícone + cor.

## 5. Primeira coluna
### Controles compactos
- Central: estado + Ligar/Parar;
- Robô: estado + Ligar/Parar;
- Desktop: estado + alternar;
- Emergência: estado + ação explícita `PARAR TUDO`.

### Navegação
- Home;
- Tarefas;
- Histórico;
- Diagnóstico;
- Configurações.

Fila, logs e atividade não permanecem empilhados na Home.

## 6. Área central — dois destinos explícitos
### Conversar
- responde sem criar task física;
- usa contexto de projeto sanitizado;
- explica capacidades, estado e resultados;
- não chama mouse, teclado, navegador, subprocesso, Policy ou executor.

### Executar objetivo
- cria task pela API operacional;
- segue Central → Robô → Goal Runtime → evidência → GoalVerifier;
- atualiza a Home somente com estados reais.

`Enter` fica no caminho de conversa por padrão. Execução física exige ação explícita distinta.

## 7. Estados da execução
```text
ENFILEIRADO
→ INTERPRETANDO
→ PLANEJANDO
→ EXECUTANDO
→ VERIFICANDO
→ SUCCEEDED | FAILED | BLOCKED
```

Nenhum receipt isolado autoriza `SUCCEEDED`.

## 8. Agente agora
Exibir apenas dados disponíveis:
- status;
- motor/estratégia;
- provider/modelo quando realmente usados;
- intent/capability;
- etapa atual/total;
- GoalVerifier;
- task id / goal id;
- duração.

Quando ocioso, o painel pode recolher para devolver espaço ao chat.

## 9. Cartão de resultado
### Sucesso
- `Objetivo concluído`;
- resumo do objetivo;
- etapas;
- readback/evidência resumida;
- `GoalVerifier: SUCCEEDED`;
- `IA usada: SIM/NÃO`;
- `Ver execução completa`.

### Falha/bloqueio
- etapa onde parou;
- critério pendente;
- causa sanitizada;
- próxima ação segura;
- link para detalhes.

## 10. Contexto de conversa
Permitido:
- identidade do projeto;
- objetivo vigente;
- arquitetura resumida;
- decisões pertinentes;
- estado operacional não sensível;
- task/goal ativo quando necessário;
- proveniência/versão.

Proibido:
- `.env`;
- chaves/tokens/credenciais;
- logs brutos desnecessários;
- cadeia privada de raciocínio;
- dados pessoais sem necessidade.

## 11. Segurança obrigatória na implementação
- loopback preservado por padrão;
- Host/Trusted Hosts;
- Origin/CSRF para mutações browser-originated;
- CORS restritiva;
- Conversation API separada de Task API;
- proteção de `clear emergency`;
- nenhuma afirmação de segurança para Internet sem arquitetura remota própria.

## 12. Acessibilidade
- WCAG 2.2 AA;
- teclado completo;
- foco visível;
- labels acessíveis;
- status não dependem apenas de cor;
- regiões de status/alerta adequadas;
- zoom 200%;
- reduced motion;
- alvos clicáveis confortáveis apesar do visual compacto.

## 13. Finding técnico a corrigir antes do redesign funcional
O parser atual não normaliza o modificador `exatamente:` em `_extract_written_text()`. A implementação futura deve começar por teste regressivo que demonstre FAIL, correção geral e PASS.

## 14. Drift documental
`README.md` ainda aponta integração do Goal Runtime como próximo passo, enquanto `docs/STATUS.md` registra a integração e validação como concluídas. A documentação deve ser sincronizada no ciclo de implementação.

## 15. Backlog preservado
O journal/idempotência durável por `task_id + action_key` continua necessário para a janela residual de crash/replay descrita em `docs/NEXT.md`; ele não é apagado pelo redesign da Home.

## 16. Critérios de aceite da futura implementação
- status visual = estado real;
- Conversar cria zero task e zero ação física;
- Executar usa o pipeline existente;
- sucesso somente após GoalVerifier;
- IA identifica o projeto a partir de contexto sanitizado;
- provider/modelo não são fabricados;
- Emergency Stop continua independente;
- segurança e acessibilidade passam nos testes;
- teste físico `Validação real número 1` passa com readback exato.

## 17. Ordem recomendada de implementação futura
1. regressão/correção `exatamente:`;
2. sincronização documental;
3. contratos de Home/telemetria;
4. Conversation Service isolado;
5. UI V4.1;
6. hardening;
7. testes automatizados e acessibilidade;
8. teste físico Linux/X11;
9. auditoria e gate.

## Decisão
`PASS` — esta é a especificação recomendada da Home para a missão atual.

## Handoff
**Carmem → Emily**

Entrega: especificação final consolidada.
Próxima ação: auditar cobertura, consistência e ausência de extrapolação.
Critério de conclusão: zero blocker para fechar a fase documental e findings futuros claramente preservados.