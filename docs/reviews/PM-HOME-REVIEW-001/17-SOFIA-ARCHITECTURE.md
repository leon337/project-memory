# PM-HOME-REVIEW-001 — Sofia — Arquitetura de Software

## Entrada recebida
Requisitos de produto/experiência e baseline técnico do `project-memory`.

## Trabalho executado
Definição das fronteiras arquiteturais da Home V4.1 sem alterar o Goal Runtime vigente.

## Evidências do baseline
`docs/STATUS.md` registra o fluxo real vigente:
`Painel → Central → SQLite/lease → Robô → interpretação/decomposição → GoalContract/GoalRunState → Capability Resolver → Policy → execução → Receipt → percepção → EvidenceRecord → GoalVerifier`.

Não existe caminho autorizado a concluir task fora do `GoalVerifier`.

## Arquitetura proposta da Home
```text
HOME UI
├─ Conversation API/Service
│  ├─ contexto de projeto sanitizado
│  ├─ resposta informacional
│  └─ PROIBIDO chamar executores físicos
│
├─ Task Command API
│  └─ pipeline existente Central → Robô → Goal Runtime
│
├─ Status/Telemetry Read API
│  └─ somente leitura do estado real
│
└─ Control API
   ├─ Central
   ├─ Robô
   ├─ Desktop
   └─ Emergência
```

## Invariantes
1. `Conversar` e `Executar objetivo` não podem ser apenas dois estilos visuais apontando para o mesmo endpoint.
2. Conversa não cria `task_id` nem aciona mouse, teclado, navegador, subprocesso ou Policy.
3. Execução sempre entra no pipeline atual e mantém `GoalVerifier` como autoridade final.
4. A Home consome telemetria; não inventa estado nem mantém uma segunda verdade paralela.
5. Contexto conversacional deve ser versionado, sanitizado e separado de segredos/`.env`/logs brutos.
6. A futura exposição remota não deve reutilizar diretamente endpoints localhost sem nova arquitetura de autenticação/autorização.

## Decisão
`PASS`.

## Handoff
**Sofia → Rafael**

Entrega: fronteiras Conversar/Executar/Telemetria/Controle e invariantes.
Próxima ação: transformar a arquitetura em plano de engenharia incremental e verificável.
Critério de conclusão: slices implementáveis após aprovação, com dependências, testes e riscos explícitos.