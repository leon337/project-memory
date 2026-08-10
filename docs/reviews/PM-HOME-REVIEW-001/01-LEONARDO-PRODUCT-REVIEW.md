# PM-HOME-REVIEW-001 — Leonardo — Produto e Requisitos

## Entrada
- quatro propostas visuais V1–V4 fornecidas por LEANDRO;
- baseline reconciliado por Miriam;
- Home deve ser centro operacional do operador digital local;
- zero alteração funcional antes do HUMAN_GATE.

## Problema de produto
A Home atual precisa permitir que LEANDRO entenda, em poucos segundos, três coisas sem abrir páginas técnicas: **o Robô está pronto?**, **o que ele está fazendo agora?** e **como eu converso ou delego um objetivo sem ambiguidade?**

## Comparação V1–V4

### V1
**Força:** transparência operacional alta; fila, logs e atividade ficam visíveis.  
**Problema:** comporta-se mais como dashboard técnico que como Home; o chat perde prioridade e a densidade cognitiva é alta.  
**Uso recomendado:** aproveitar seus detalhes em Tarefas, Histórico e Diagnóstico, não como composição principal da Home.

### V2
**Força:** separa controles, conversa e painel do agente; bom equilíbrio operacional.  
**Problema:** coluna de controles é visualmente pesada e compete com a conversa; ainda parece console de operação.  
**Uso recomendado:** reaproveitar a clareza do painel “Agente agora” e a noção de controles explícitos, porém compactados.

### V3
**Força:** melhor foco conversacional e menor carga visual.  
**Problema:** esconde demais o estado real do Robô; execução e conversa ainda podem parecer o mesmo ato; oferece pouca prova do Goal Runtime.  
**Uso recomendado:** aproveitar espaço, calma visual e foco central da conversa.

### V4
**Força:** melhor combinação entre chat, estado do sistema e execução verificável; o cartão de conclusão explicita Motor, IA, etapas, readback e GoalVerifier.  
**Problema:** ainda precisa separar de modo impossível de confundir “conversar” de “executar”, e os status/controles devem vir somente de telemetria real.  
**Uso recomendado:** **base candidata V4.1**, sujeita ao HUMAN_GATE de LEANDRO.

## Decisão de produto recomendada
A Home não deve ser um dashboard completo nem um chat puro. Deve ser uma **Home híbrida de operação**, com a conversa no centro e transparência suficiente para comprovar execução.

### Tarefas primárias da Home
1. Conversar com a IA sem acionar o computador.
2. Delegar um objetivo para execução física de forma explícita.
3. Ver imediatamente estado real de Central, Robô, Sistema/desktop, IA e Emergência.
4. Acompanhar a etapa atual de um Goal em execução.
5. Ver resultado e evidência resumida após o `GoalVerifier`.
6. Navegar para detalhes quando necessário, sem poluir a Home.

## Requisitos de produto obrigatórios

### PR-01 — Dois modos sem ambiguidade
A entrada deve possuir dois destinos explícitos:
- **Conversar** — resposta informacional; não cria task física e não aciona executor.
- **Executar objetivo** — cria um Goal/Task no pipeline existente.

Não aceitar um único botão cuja intenção seja inferida silenciosamente.

### PR-02 — Verdade operacional
Nenhum estado visual pode ser meramente decorativo. Central, Robô, Sistema/desktop, IA e Emergência devem refletir dados reais.

### PR-03 — Sucesso somente do GoalVerifier
O cartão “Objetivo concluído” só aparece depois de `GoalVerifier=SUCCEEDED`. Receipt, provider ou executor isolado não autorizam esse estado.

### PR-04 — Evidência resumida
Após uma execução, mostrar no mínimo:
- etapas concluídas/total;
- verificação/readback quando aplicável;
- GoalVerifier;
- link “Ver execução completa”.

### PR-05 — Estado do agente em tempo real
O bloco “Agente agora” deve apresentar somente campos realmente disponíveis: status, etapa atual, intent/capability, provider/modelo quando de fato usados, task/goal id e duração.

### PR-06 — Controles compactos
Controles de Central, Robô, Desktop e Emergência devem ficar compactos e secundários, preferencialmente na coluna lateral. A Home não deve dedicar grandes cards a controles básicos.

### PR-07 — Progressive disclosure
Fila detalhada, logs brutos, diagnóstico, modelos, configuração e histórico pertencem às páginas especializadas. A Home mostra apenas resumo e links.

### PR-08 — Conversa contextual ao projeto
A IA de conversa deve receber um contexto sanitizado e versionado do projeto suficiente para responder perguntas como “em qual projeto você está?” sem inventar estado.

### PR-09 — Falha útil
Em falha, a Home deve mostrar: onde parou, qual critério ficou pendente, mensagem compreensível e ação segura seguinte; nunca converter falha em “concluído”.

### PR-10 — Sem alteração de governança
A Home não pode contornar Policy, Emergency Stop, FAILSAFE, foco, lease ou GoalVerifier.

## Critérios de aceite de produto
- usuário diferencia Conversar de Executar sem ler documentação;
- estado de execução visível em até um olhar;
- sucesso visual corresponde ao verdict real;
- detalhes técnicos existem, mas não dominam a Home;
- V4.1 preserva a conversa como centro e a verificabilidade como segunda prioridade;
- nenhuma recomendação desta revisão altera `main` antes do HUMAN_GATE.

## Verdict
`PASS_WITH_CHANGES`

**Recomendação:** usar V4 como base estrutural e absorver a leveza da V3, a transparência detalhada da V1 nas páginas secundárias e a clareza operacional da V2 em controles compactos.

## Handoff
**Leonardo → Evelyn**  
Próxima ação: transformar os requisitos de produto em jornada e estados de experiência, mantendo Conversar e Executar semanticamente separados.