# PM-HOME-REVIEW-001 — Carmem — Especificação Consolidada Home V4.1

> **Status:** recomendação para HUMAN_GATE. Não é decisão final e não autoriza implementação.

## 1. Objetivo da Home
Ser a superfície principal do Robô para **conversar, delegar objetivos, acompanhar execução real e compreender o estado do sistema**, sem obrigar o operador a usar um dashboard técnico.

## 2. Base visual
**V4** é a base recomendada, com incorporação seletiva de:
- V3: foco e espaço da conversa;
- V2: clareza do painel “Agente agora” e dos controles;
- V1: profundidade de fila/logs apenas em páginas secundárias.

## 3. Layout desktop

```text
┌────────────────────────────────────────────────────────────────────┐
│ PAINEL DO ROBÔ        status compactos                  sessão     │
├──────────────┬───────────────────────────────────┬─────────────────┤
│ Navegação    │ Conversar com a IA                │ Agente agora    │
│              │                                   │                 │
│ Controles    │ histórico da conversa / Goal      │ status          │
│ compactos    │                                   │ etapa           │
│              │ [campo de mensagem]               │ intent/cap.     │
│ Central      │ [CONVERSAR] [EXECUTAR OBJETIVO]   │ provider        │
│ Robô         │                                   │ verifier        │
│ Desktop      │ atalhos contextuais               │ task/goal id    │
│ Emergência   │                                   │ duração         │
└──────────────┴───────────────────────────────────┴─────────────────┘
```

## 4. Status superior
Uma linha horizontal compacta, sempre baseada em telemetria real:
- Central;
- Robô local;
- Sistema/desktop;
- IA;
- Emergência.

Sem cards altos. Estado textual acompanha ícone/cor.

## 5. Coluna lateral
### Navegação
- Home
- Tarefas
- Histórico
- Diagnóstico
- Configurações

### Controles de estado
Compactos, com estado e ação separados:
- Central: `ONLINE` / `Ligar` ou `Parar`;
- Robô: `ONLINE` / `Ligar` ou `Parar`;
- Desktop: `ATIVO` / alternar;
- Emergência: `NORMAL` / `PARAR TUDO`;

`Limpar emergência` não deve ser confundido com o próprio botão de parada.

## 6. Área central — dois modos

### Conversar
- não cria task física;
- pode responder sobre o projeto usando contexto sanitizado;
- pode explicar capacidades, estado e próximos passos;
- não chama mouse/teclado/processos/browser executores.

### Executar objetivo
- envia texto para Central/Task API;
- percorre fila → Robô → Goal Runtime → evidência → GoalVerifier;
- UI acompanha estados reais.

### Regra de teclado
`Enter` deve permanecer associado ao modo Conversar por padrão. Execução física exige ação explícita “Executar objetivo” ou atalho claramente distinto e documentado.

## 7. Estados do Goal na Home

```text
ENFILEIRADO
→ INTERPRETANDO
→ PLANEJANDO
→ EXECUTANDO
→ VERIFICANDO
→ SUCCEEDED | FAILED | BLOCKED
```

A UI não pode saltar diretamente de envio para “concluído” com base apenas em receipt.

## 8. Cartão “Agente agora”
Campos exibidos somente quando existem:
- status;
- motor/estratégia;
- provider/modelo quando usados;
- intent/capability;
- etapa atual/total;
- GoalVerifier;
- task id / goal id;
- duração.

Nunca usar placeholders que pareçam telemetria real.

## 9. Cartão final
### Sucesso
Título: `Objetivo concluído`

Mostrar:
- objetivo resumido;
- etapas completas;
- verificação/readback resumido;
- `GoalVerifier: SUCCEEDED`;
- IA usada: sim/não;
- botão `Ver execução completa`.

### Falha/bloqueio
Mostrar:
- etapa onde parou;
- critério pendente;
- causa sanitizada;
- próxima ação segura;
- link para detalhes.

## 10. Contexto de projeto para conversa
Contexto mínimo, versionado e sanitizado:
- identidade do projeto;
- objetivo atual;
- arquitetura resumida;
- decisões vigentes pertinentes;
- estado operacional público;
- task ativa quando apropriado.

Proibido incluir `.env`, chaves, credenciais, segredo, logs brutos ou cadeia de pensamento.

## 11. Segurança
Antes de considerar a Home pronta:
- bind loopback preservado;
- trusted hosts/Host validation;
- Origin/CSRF para mutações browser-originated;
- CORS restritiva;
- separação técnica Conversar/Executar;
- `clear emergency` protegido;
- nenhuma reutilização direta desses endpoints para acesso remoto futuro.

## 12. Acessibilidade
- WCAG 2.2 AA;
- foco visível;
- labels acessíveis;
- estados não dependem só de cor;
- `aria-live`/status/alert adequados;
- zoom 200%;
- reduced motion;
- controles principais confortáveis para toque/clique.

## 13. Observabilidade
Timeline derivada de eventos reais:
`Recebido → Interpretando → Executando → Verificando → Concluído/Falhou`.

Detalhes e logs brutos ficam fora da Home.

## 14. Ordem de implementação recomendada após aprovação
1. corrigir/regredir `exatamente:`;
2. sincronizar documentação do Goal Runtime;
3. definir contrato da Home/telemetria;
4. implementar Conversar isolado;
5. implementar redesign V4.1;
6. aplicar hardening;
7. validar automaticamente;
8. validar fisicamente;
9. auditoria e gate final.

## 15. Critérios de aceite da Home V4.1
- status visual = estado real;
- Conversar nunca executa;
- Executar sempre usa pipeline existente;
- sucesso somente por GoalVerifier;
- IA sabe identificar o projeto por contexto explícito e sanitizado;
- V4.1 funciona por teclado e com leitor de tela;
- Emergency Stop continua independente;
- nenhuma credencial ou cadeia privada de raciocínio exibida/persistida;
- testes automatizados e físicos obrigatórios passam.

## 16. Handoff
**Carmem → Gabriel**  
Próxima ação: verificar rastreabilidade Git da revisão e preparar o pacote para auditoria independente, sem abrir PR/merge antes do HUMAN_GATE.