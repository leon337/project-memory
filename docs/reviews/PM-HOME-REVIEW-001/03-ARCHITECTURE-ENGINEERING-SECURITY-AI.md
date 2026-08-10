# PM-HOME-REVIEW-001 — Arquitetura, Engenharia, Segurança e IA

## Sofia — Arquitetura

### Princípio
A nova Home deve **observar e acionar o pipeline existente**, não criar um segundo runtime de execução.

### Separação obrigatória

```text
                     ┌────────────────────┐
Mensagem do usuário ─┤ Home Input         │
                     └─────────┬──────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
          CONVERSAR                    EXECUTAR OBJETIVO
                 │                           │
      Conversation Service           Central / Task API
                 │                           │
      provider + contexto             fila + lease
       sanitizado do projeto                 │
                 │                    Robô local
                 │                           │
           resposta textual           Goal Runtime
                                             │
                                        GoalVerifier
```

### Invariantes
- `Conversation Service` não controla mouse, teclado, browser ou processos;
- `Executar objetivo` sempre entra no fluxo Central → fila → Robô → Goal Runtime;
- `GoalVerifier` continua autoridade exclusiva de `succeeded`;
- fast paths permanecem internos ao Goal Runtime;
- Policy, FAILSAFE, foco, lease e Emergency Stop não são duplicados no frontend.

### Contexto de conversa
Criar um snapshot pequeno e sanitizado derivado das fontes oficiais do projeto, com campos como:
- nome/identidade do projeto;
- objetivo atual;
- arquitetura resumida;
- decisões vigentes relevantes;
- estado operacional público do painel;
- task ativa quando aplicável.

Não enviar `.env`, tokens, credenciais, logs brutos ou conteúdo pessoal desnecessário ao provider.

### View model recomendado
Uma única visão de estado da Home pode agregar dados já existentes sem transformar o frontend em orquestrador:

```json
{
  "system": {},
  "active_task": {},
  "goal": {},
  "conversation": {},
  "controls": {}
}
```

Pode ser implementada como endpoint agregado ou composição cliente, desde que a fonte de cada campo permaneça rastreável.

### Entrega
`PASS` — arquitetura V4.1 aprovada como conceito, com Conversar isolado de Executar.

**Handoff: Sofia → Rafael** — definir slices de implementação e regressão sem mudar as invariantes.

---

## Rafael — Engenharia

### Findings técnicos obrigatórios
1. reproduzir o caso `escreva exatamente:` antes do redesign funcional;
2. adicionar regressão dedicada no parser/interpreter;
3. não vincular redesign visual a refactor do Goal Runtime;
4. preservar a bateria existente e o CI;
5. implementar Home em slices pequenos e verificáveis.

### Plano de implementação proposto após HUMAN_GATE

#### Slice 1 — correções de baseline
- teste FAIL para `exatamente:`;
- correção mínima do parser;
- teste PASS;
- sincronizar README com STATUS/ARCHITECTURE;
- nenhuma mudança visual ainda.

#### Slice 2 — contrato de Home
- definir tipos/DTOs da visão agregada;
- testes de estado real para Central, Robô, desktop, IA e emergência;
- nenhum dado mock no runtime.

#### Slice 3 — Conversar vs Executar
- endpoint/serviço de conversa sem execução física;
- endpoint de execução continua sendo o pipeline de tasks;
- testes negativos garantindo que Conversar não cria task.

#### Slice 4 — V4.1 UI
- layout, status compactos, controles laterais e painel Agente agora;
- estados queued/running/verifying/succeeded/failed;
- acessibilidade.

#### Slice 5 — hardening e observabilidade
- controles de fronteira definidos por Segurança;
- eventos de telemetria definidos por Augusto;
- regressões de segurança.

#### Slice 6 — validação física
- testes de Renato pelo fluxo real;
- evidência visual + readback/GoalVerifier quando aplicável.

### TDD
Cada mudança deve começar por um teste que falhe pelo comportamento esperado. Nenhum bug deve ser considerado corrigido somente por inspeção estática.

### Entrega
`PASS_WITH_CHANGES` — implementar somente depois do HUMAN_GATE e sem misturar redesign com reescrita do core.

**Handoff: Rafael → Ricardo** — modelar ameaças da nova superfície e controles mínimos.

---

## Ricardo — Segurança

### Contexto
O Painel é localhost por decisão vigente, mas recebe comandos capazes de iniciar/parar serviços, alterar desktop e submeter objetivos físicos. Loopback reduz exposição de rede; não elimina riscos vindos do navegador local.

### Ameaças relevantes
- requisições cross-site para endpoints mutáveis;
- DNS rebinding / Host inesperado;
- script malicioso em página aberta no navegador tentando chamar localhost;
- confusão entre Conversar e Executar;
- vazamento de prompt/contexto/log em providers;
- limpeza indevida do Emergency Stop;
- futura exposição remota reutilizando endpoints locais sem camada própria.

### Controles mínimos propostos
1. bind explícito em loopback;
2. validação de `Host`/trusted hosts;
3. política CORS restritiva/ausente por padrão;
4. proteção de Origin/CSRF para mutações iniciadas pelo browser;
5. token/sessão local de painel quando aplicável, sem gravar segredo em HTML/log;
6. `trigger emergency` pode privilegiar disponibilidade de segurança, mas `clear emergency` exige autenticação/controle mais forte;
7. nenhuma credencial em contexto conversacional;
8. sanitização antes de persistir/mostrar resultado;
9. modo Conversar incapaz de invocar executores;
10. acesso remoto futuro deve possuir gateway/autenticação próprios; nunca “abrir a porta” do localhost diretamente.

### Observação
A ausência explícita desses controles em `dashboard.py` é um **finding de hardening**, não prova de comprometimento atual. O threat model considera a arquitetura localhost e o browser como fronteira relevante.

### Entrega
`PASS_WITH_CHANGES` — V4.1 é aceitável se o hardening entrar antes de qualquer acesso remoto e junto da separação Conversar/Executar.

**Handoff: Ricardo → Tiago** — definir comportamento da IA, roteamento e grounding do chat.

---

## Tiago — IA / Modelos e Integração

### Objetivo da IA na Home
A Home deve evidenciar quando a IA está **conversando**, quando está **interpretando/decompondo um objetivo** e quando **não foi necessária**.

### Regras de roteamento
- comandos determinísticos continuam sem provider quando o runtime já sabe executá-los;
- conversa informacional usa provider, mas sem acesso direto a executores;
- objetivos `GENERIC` podem usar provider para decomposição estruturada conforme arquitetura vigente;
- fallback de provider ocorre no raciocínio, não repete cegamente ação física já executada;
- `IA usada: NÃO` é um estado válido e desejável em fast paths.

### Grounding da conversa
Para a pergunta “em qual projeto você está?”, a resposta deve vir de um **Project Context Snapshot** sanitizado, não de memória implícita do modelo. O snapshot deve declarar proveniência e versão/atualização quando possível.

### Campos úteis no painel
- provider/modelo somente quando houve chamada;
- motivo resumido do uso: conversa, decomposição, replanejamento;
- fallback, quando ocorreu;
- nunca exibir prompt interno, cadeia de pensamento, token/chave ou contexto sensível.

### Falha de IA
Indisponibilidade de provider não deve derrubar fast paths determinísticos. Em conversa, a UI deve apresentar indisponibilidade de IA sem fingir resposta; em execução genérica, o Goal permanece pendente/falha conforme contrato e evidência real.

### Entrega
`PASS` — a nova Home deve mostrar IA como componente do sistema, não como autoridade final de execução.

**Handoff: Tiago → Beatriz** — definir avaliação objetiva de grounding, separação de modos e qualidade do comportamento do agente.