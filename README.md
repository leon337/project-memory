# Robô Operador — MVP 0.3

Operador digital local em Linux/X11 com **Painel do Robô**, Central, fila persistente e Robô executor.

> O estado oficial e detalhado do projeto está em `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` e `docs/NEXT.md`. Este README é apenas uma visão rápida.

## Arquitetura atual

```text
Usuário
  ↓
Painel do Robô — 127.0.0.1:8765
  ↓
Central — 127.0.0.1:8000
  ↓
SQLite — fila / leases / histórico
  ↓
Robô local
  ↓
Goal Runtime universal
  ↓
Interpretação tipada / MultiProviderPlanner
  ├─ Z.AI / GLM
  ├─ Google Gemini
  └─ Cloudflare Workers AI
  ↓
Capability Resolver
  ↓
Policy Layer
  ↓
Executores
  ├─ Playwright / Chromium
  └─ Desktop Linux / PyAutoGUI / subprocess
  ↓
ExecutionReceipt
  ↓
Observação / readback independente
  ↓
EvidenceRecord
  ↓
GoalVerifier
```

O **Goal Runtime universal já está integrado ao fluxo real**. O estado `succeeded` representa objetivo completo comprovado por critérios e evidências; uma ação executada ou um `ExecutionReceipt` isolado não conclui a tarefa.

## Estado já validado fisicamente

No Linux/X11 real já foram validados, entre outros:

- Painel, Central e Robô como processos separados;
- ligar/parar/reiniciar pelo Painel;
- telemetria real;
- Emergency Stop persistente;
- FAILSAFE físico nos cantos;
- screenshot, mouse e teclado;
- digitação Unicode;
- proteção de foco;
- abertura de aplicativos;
- navegação e pesquisa;
- planner multi-provider com fallback;
- fast paths locais como `editor + escrever` e `navegador + pesquisa`;
- Goal Runtime integrado ao `local_agent.py`;
- conclusão de objetivos condicionada ao `GoalVerifier` e a evidência independente.

O baseline de autonomia também demonstrou limitações reais de interpretação, percepção, resolução de capacidades, contexto entre tarefas e um caso histórico de falso `succeeded` em objetivo composto. Esses resultados estão documentados em `docs/STATUS.md`.

## Goal Runtime — integrado

O fluxo vigente é:

```text
Goal Contract
→ estado operacional
→ subobjetivos / capabilities
→ próxima etapa
→ Policy Layer
→ executor
→ Execution Receipt
→ observação
→ EvidenceRecord
→ GoalVerifier
→ continuar/replanejar ou succeeded
```

Componentes principais:

- `src/context_anchor/goal_runtime.py` — contratos, critérios, evidências e autoridade final de conclusão;
- `src/context_anchor/goal_execution.py` — orquestração dos fast paths e decomposições estruturadas;
- `src/context_anchor/local_agent.py` — integração do Goal Runtime ao fluxo Painel → Central → Robô;
- `tests/test_goal_runtime_contract.py` e demais regressões — cobertura automatizada do runtime.

A missão histórica e seus critérios continuam documentados em `docs/CODEX_GOAL_RUNTIME_MISSION.md`.

## Regra de conclusão

Ação executada não significa objetivo concluído.

Um `ExecutionReceipt` registra apenas sucesso técnico. Todo critério obrigatório precisa de evidência compatível antes de o `GoalVerifier` permitir `succeeded`.

## Fast paths e IA

Fast paths determinísticos continuam importantes para latência e economia de quota, mas são **skills internas do mesmo Goal Run**, não um caminho paralelo de conclusão.

IA fica reservada para interpretação semântica, decomposição, condição, ambiguidade e replanejamento. Providers são intercambiáveis e podem fazer fallback antes da ação física correspondente.

## Perfil local

O perfil local confiável é **permissivo por padrão**: ausência de cadastro prévio não deve ser, por si só, motivo para bloquear uma capacidade disponível ao usuário e ao sistema operacional. Bloqueios específicos futuros entram como regras explícitas/denylist.

Continuam independentes do raciocínio:

- Emergency Stop;
- FAILSAFE;
- verificação de foco;
- Policy Layer;
- credenciais fora de Git/logs/prompts.

Painel e Central permanecem em localhost e esta versão não deve ser publicada diretamente na Internet.

## Requisitos

- Python 3.11+;
- Linux desktop;
- sessão X11 no backend físico atual;
- Chromium do Playwright;
- `xdotool` e `scrot` para recursos atuais de percepção.

Linux Mint/Ubuntu:

```bash
sudo apt update
sudo apt install -y xdotool scrot
```

## Instalação

```bash
git clone https://github.com/leon337/project-memory.git
cd project-memory
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m playwright install chromium
cp .env.example .env
```

As credenciais e tokens ficam somente no `.env` local.

## Operação

Com a `.venv` ativa:

```bash
painel-robo
```

Painel:

```text
http://127.0.0.1:8765
```

Também existem comandos técnicos como:

```bash
central
robo
diagnostico-robo
parar-robo status
```

O Painel é a interface principal para operação normal.

## Testes

```bash
pytest
```

O GitHub Actions executa instalação, compilação e testes automatizados. Mudanças em desktop/browser/Goal Runtime continuam sujeitas às regressões e aos testes físicos aplicáveis descritos na documentação do projeto.

## Próximo ciclo

A evolução atual é a **Home V4.1** do Painel do Robô: conversa com IA separada tecnicamente de execução, telemetria real compacta, acompanhamento do Goal Runtime, hardening da fronteira browser/localhost e acessibilidade. A implementação é rastreada pela missão `PM-HOME-IMPLEMENT-001`.
