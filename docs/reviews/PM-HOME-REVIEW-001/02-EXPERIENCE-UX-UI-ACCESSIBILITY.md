# PM-HOME-REVIEW-001 — Experiência, UX, UI e Acessibilidade

## Evelyn — Experiência e Jornada

### Entrada
Requisitos de Leonardo: Home híbrida, conversa central, execução explícita, verdade operacional e sucesso somente pelo GoalVerifier.

### Jornada recomendada

```text
HOME OCIOSA
→ usuário escreve
→ escolhe CONVERSAR ou EXECUTAR OBJETIVO
→ sistema confirma o destino visualmente
→ processamento
→ resposta conversacional OU Goal em execução
→ execução mostra estágio real
→ verificação
→ sucesso/falha comprovado
→ ação seguinte clara
```

### Estados de experiência obrigatórios
1. `PRONTO` — sistema utilizável.
2. `CONVERSANDO` — IA responde sem criar task física.
3. `ENFILEIRADO` — objetivo aceito pela Central.
4. `INTERPRETANDO/PLANEJANDO` — intent/decomposição em andamento.
5. `EXECUTANDO` — ação física em curso.
6. `VERIFICANDO` — percepção/evidência/GoalVerifier.
7. `CONCLUÍDO` — somente verdict real.
8. `FALHOU/BLOQUEADO` — causa e próximo passo seguro.

### Redução de ansiedade operacional
Não mostrar logs brutos no centro da Home. Mostrar progresso legível e permitir expansão sob demanda. O operador deve perceber atividade real sem acompanhar linhas técnicas continuamente.

### Entrega
`PASS` — V4 é a melhor base de jornada, desde que o seletor Conversar/Executar seja estrutural e não apenas visual.

**Handoff: Evelyn → Laura** — transformar a jornada em arquitetura de informação e interação.

---

## Laura — UX e Arquitetura de Informação

### Arquitetura da Home

```text
┌─────────────────────────────────────────────────────────────┐
│ Header: identidade + status compacto + sessão              │
├───────────────┬───────────────────────────┬─────────────────┤
│ Navegação     │ Conversa / execução       │ Agente agora    │
│ + controles   │                           │                 │
│ compactos     │                           │                 │
├───────────────┴───────────────────────────┴─────────────────┤
│ atalhos contextuais / links secundários                   │
└─────────────────────────────────────────────────────────────┘
```

### Regras de interação
- um único campo de mensagem pode ser mantido, mas o destino precisa de dois controles persistentes: **Conversar** e **Executar objetivo**;
- Enter não deve executar ação física por acidente; padrão seguro: Enter envia no modo Conversar e execução exige botão explícito ou atalho distinto claramente informado;
- durante Goal ativo, o painel direito fixa etapa atual sem impedir nova conversa;
- o cartão final substitui progresso somente quando o verdict muda;
- “Ver detalhes” abre execução/evidências, não uma página genérica;
- os atalhos “Abrir editor”, “Navegar web”, “Listar arquivos” devem deixar claro se são exemplos de objetivo, não botões mágicos com semântica diferente do pipeline.

### Navegação
Home, Tarefas, Histórico, Diagnóstico, Configurações. Logs e fila entram nas páginas especializadas; não precisam de widgets permanentes na Home.

### Entrega
`PASS_WITH_CHANGES` — manter estrutura V4, tornar o destino da entrada semanticamente explícito e reduzir caminhos paralelos de execução.

**Handoff: Laura → Isabela** — traduzir a hierarquia em sistema visual consistente.

---

## Isabela — UI / Design Visual

### Composição recomendada V4.1
- fundo ultra-dark mantido;
- coluna lateral estreita com navegação e controles de estado compactos;
- faixa superior de status em **uma única linha horizontal compacta**;
- chat ocupa a maior área útil;
- painel “Agente agora” permanece à direita em desktop;
- cartões de sucesso/falha são estados do fluxo, não blocos decorativos permanentes.

### Hierarquia
1. mensagem/objetivo;
2. resposta ou progresso;
3. estado do agente;
4. estado global;
5. navegação/configuração.

### Status compactos
Exibir ícone + rótulo curto + estado:
- Central · Online/Offline;
- Robô · Online/Offline;
- Sistema · Saudável/Problema;
- IA · Disponível/Indisponível;
- Emergência · Normal/Ativa.

Evitar cards altos. O estado deve caber em uma linha e não roubar altura do chat.

### Controles laterais
Botões pequenos, mas claros, para Central, Robô, Desktop e Emergência. Estado e ação devem ser distinguíveis: ex. `Robô: ONLINE` + ação `Parar`, não um botão cujo texto muda sem contexto.

### Cartão de resultado
Manter a ideia visual da V4, porém usar:
- título “Objetivo concluído”;
- resumo do objetivo;
- `Etapas`, `Verificação`, `GoalVerifier`;
- `IA usada` apenas se houve provider;
- ação “Ver execução completa”.

### Responsividade
Em largura menor, “Agente agora” deve cair abaixo do chat; a navegação pode colapsar, sem esconder Emergência.

### Entrega
`PASS` — V4.1 deve preservar a densidade visual da V4, mas com controles mais compactos e estados sempre reais.

**Handoff: Isabela → Marina** — validar acessibilidade e interação inclusiva.

---

## Marina — Acessibilidade

### Requisitos mínimos
- contraste WCAG 2.2 AA para textos, estados e botões;
- foco de teclado altamente visível;
- ordem de tabulação acompanha a hierarquia visual;
- controles com nome acessível completo, não apenas ícone;
- status não pode depender somente de verde/vermelho;
- mensagens de execução e conclusão anunciadas via região `aria-live` adequada;
- alvos interativos confortáveis; preferir 44×44 CSS px para controles principais;
- suporte a zoom de 200% sem perda de função;
- `prefers-reduced-motion` para animações de pulso/progresso;
- labels persistentes para o seletor Conversar/Executar;
- erros associados ao campo e à tarefa correspondente;
- Emergency Stop deve permanecer localizável por teclado e leitor de tela.

### Semântica recomendada
- `nav` para menu;
- `main` para conversa;
- `aside` para “Agente agora”;
- botões reais para ações;
- `role=status` para estado não urgente;
- `role=alert` somente para falhas/emergência que exigem atenção imediata.

### Entrega
`PASS_WITH_CHANGES` — a proposta visual é viável, mas acessibilidade precisa ser critério de implementação e teste, não revisão posterior.

**Handoff: Marina → Sofia** — projetar componentes e contratos técnicos que preservem esses estados sem criar um pipeline paralelo.