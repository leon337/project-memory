# ARCHITECTURE

## Terminologia usada

- **Painel do Robô** = gerenciador local de operação, configuração, diagnóstico e aprendizado;
- **Central** = processo técnico `Control Plane`;
- **Robô local** = processo técnico `local agent`.

## Arquitetura implementada no MVP 0.3

```text
Usuário
  ↓
Painel do Robô — FastAPI :8765
  ├─ estado real / configuração / diagnóstico / aprendizado
  ├─ controles de processo orientados pelo estado atual
  ├─ tarefas recentes
  ├─ telemetria real de Painel / Central / Robô
  └─ envio de tarefa
          ↓
Central — FastAPI :8000
          ↓
SQLite — fila, histórico e leases
          ↓
HTTP polling autenticado
          ↓
Robô local
          ↓
Planner
  ├─ DeterministicPlanner ativo
  └─ ProviderPlanner provider-agnostic
          ↓
StructuredAction
          ↓
Policy Layer
  ├─ navegador
  └─ desktop + feature gate
          ↓
Executores
  ├─ Playwright / Chromium
  └─ PyAutoGUI / Linux X11
          ↓
Verificação
          ↓
Central / Painel do Robô
```

Painel, Central e Robô são processos separados para que o Painel continue disponível mesmo quando Central ou Robô forem reiniciados.

## 1. Painel do Robô

Implementado em `src/context_anchor/dashboard.py`.

Comando humano: `painel-robo`.

Bind padrão: `127.0.0.1:8765`.

Responsabilidades atuais:

- mostrar estado de Central, Robô, Desktop e emergência;
- iniciar/parar Central;
- iniciar/parar/reiniciar Robô;
- alterar configurações locais explicitamente suportadas;
- executar diagnóstico de leitura;
- mostrar tarefas recentes e telemetria real;
- enviar tarefas à Central;
- explicar comandos de desenvolvimento no Laboratório.

O Painel não possui endpoint de shell arbitrário.

## 2. Central

Implementada em `src/context_anchor/control_plane.py`.

Responsabilidades:

- autenticação separada de usuário e Robô;
- criação e consulta de tarefas;
- persistência;
- entrega de tarefa ao Robô;
- emissão de lease;
- recepção de resultado protegido pelo lease;
- registro de eventos operacionais.

Bind padrão: `127.0.0.1:8000`.

## 3. Persistência e leases

Implementada em `src/context_anchor/store.py` com SQLite.

Fluxo:

```text
queued
  ↓ claim + lease
running
  ↓
succeeded | failed
```

Tarefa abandonada pode retornar à fila após expiração do lease. Resultados atrasados com lease antigo são rejeitados.

## 4. Robô local

Implementado em `src/context_anchor/local_agent.py`.

Fluxo:

1. verifica parada de emergência;
2. registra identidade do processo;
3. autentica na Central;
4. busca tarefa;
5. obtém plano;
6. valida na Policy Layer;
7. executa;
8. verifica;
9. envia resultado;
10. registra telemetria.

## 5. Planner

Contrato em `src/context_anchor/planner.py`.

Estado atual:

- `DeterministicPlanner` é o planner ativo;
- `StructuredAction` aceita apenas ações conhecidas;
- `ProviderPlanner` existe para integração externa;
- nenhum provedor externo está ativo ainda.

A arquitetura permanece **provider-agnostic**, mas a direção definida para IA é agora **multi-provider com roteamento inteligente e quota-aware**.

Arquitetura alvo:

```text
pedido do usuário
      ↓
ProviderPlanner
      ↓
AI Router / Quota Manager
  ├─ classifica capacidade exigida
  ├─ observa quota/budget conhecido
  ├─ respeita concorrência
  ├─ mede latência
  ├─ acompanha 429 / timeout / 5xx
  └─ aplica cooldown / circuit breaker
      ↓
┌─────────────────────────────────────┐
│ Z.AI / GLM-4.7-Flash               │ → reasoning / decisões complexas
│ Cloudflare Workers AI              │ → fast planner / burst eficiente
│ Google Gemini                      │ → multimodalidade / visão / fallback
└─────────────────────────────────────┘
      ↓
adaptador do provedor escolhido
      ↓
resposta normalizada
      ↓
StructuredAction
      ↓
Policy Layer
      ↓
executor permitido
```

O roteador não usa round-robin simples. A seleção é feita por adequação à tarefa e estado operacional do provedor.

### 5.1 Papéis iniciais

**Z.AI / GLM-4.7-Flash**

- alvo principal para reasoning e decisões complexas;
- preço zero atual segundo a pesquisa/documentação auditada;
- suporta reasoning, tools e structured output;
- a conta real validada mostrou `concurrency limit = 1` para `GLM-4.7-Flash`, portanto o roteador deve serializar ou respeitar esse teto.

**Cloudflare Workers AI**

- alvo para decisões simples, frequentes e bursts;
- o rate limit default de Text Generation é alto, mas existe também budget diário em neurons;
- modelos menores/eficientes devem ser preferidos para chamadas simples para não desperdiçar o budget com reasoning pesado;
- Cloudflare AI Gateway pode futuramente ser usado como camada adicional de fallback/routing, mas não é obrigatório para o primeiro router local.

**Google Gemini**

- alvo complementar para multimodalidade, visão e capacidades próprias do ecossistema;
- também funciona como fallback compatível quando a tarefa não exigir um recurso exclusivo de outro provedor;
- limites reais são por projeto/modelo e devem ser lidos e contabilizados conforme o projeto configurado.

### 5.2 Estado por provedor

O roteador deverá manter, quando possível:

- `request_headroom`;
- `token_headroom`;
- `daily_headroom` ou budget equivalente;
- `concurrency_available`;
- latência recente;
- taxa recente de erros;
- `cooldown_until` após rate limit/falhas transitórias;
- capabilities do modelo: texto, reasoning, tools, structured output, vision.

Quando o provedor não expuser headers ou endpoint de quota suficiente, o projeto manterá contadores locais conservadores e reagirá a `429`/erros retornados pela própria API.

### 5.3 Fallback e idempotência

Fallback de provedor acontece na camada de planejamento.

Se uma chamada ao modelo falhar antes de produzir uma ação executável, outro provedor compatível pode ser tentado.

Uma ação física já executada não deve ser repetida automaticamente apenas porque uma etapa posterior do planner falhou. O estado deve ser verificado antes de nova execução.

Trocar de provedor nunca altera ou ignora:

- `StructuredAction`;
- Policy Layer;
- FAILSAFE;
- parada de emergência;
- verificação de resultado;
- regras de idempotência.

O `DeterministicPlanner` permanece como fallback técnico e para testes.

SiliconFlow permanece compatível com a estratégia provider-agnostic e pode ser adicionado depois como novo adaptador se seus limites gratuitos reais forem comprovados.

## 6. Credenciais de provedores

Chaves de API não entram em código, Git, logs ou prompts.

Cada adaptador consome sua própria chave somente por variável de ambiente/configuração local.

Contas e chaves já foram criadas externamente para SiliconFlow e Z.AI. Gemini já está disponível ao usuário. Cloudflare Workers AI ainda precisa ter sua credencial local preparada para o projeto.

Nenhuma dessas credenciais está integrada ao código neste momento.

## 7. Policy Layer

Implementada em `src/context_anchor/policy.py`.

Toda ação produzida por planner determinístico ou por IA futura passa pela mesma camada de política.

### Navegador

- apenas HTTP/HTTPS;
- localhost, `.local`, IPs privados, loopback, link-local e reservados permanecem bloqueados.

### Desktop

- feature gate `CONTEXT_ANCHOR_DESKTOP_ENABLED`;
- ações tipadas;
- coordenadas validadas;
- texto limitado;
- teclas permitidas por lista;
- aplicativos por allowlist fixa.

## 8. Navegador

Implementado em `src/context_anchor/actions.py` com Playwright/Chromium.

Preferência arquitetural:

```text
API/DOM
→ automação estruturada
→ acessibilidade
→ visão + mouse/teclado como fallback
```

## 9. Desktop

Backend em `src/context_anchor/desktop.py`.

Capacidades atuais:

- screenshot;
- janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo/direito;
- digitar texto;
- teclas permitidas;
- abrir aplicativos permitidos.

Backend físico inicial: Linux/X11.

### FAILSAFE explícito

Além de `pyautogui.FAILSAFE = True`, o backend verifica a posição atual do ponteiro antes de qualquer entrada física.

Uma margem de 20 pixels nos quatro cantos funciona como zona de interrupção. Se o ponteiro estiver nessa zona, a ação gera `DesktopFailsafeTriggered` antes de mover, clicar ou digitar.

## 10. Aplicativos

Ids conhecidos são mapeados para executáveis permitidos e abertos com `shell=False`.

O Robô não aceita linha de shell arbitrária recebida da tarefa.

## 11. Percepção

Primeiro slice implementado:

- screenshot;
- janela ativa.

Ainda faltam árvore de acessibilidade, percepção semântica da imagem e fusão de fontes de percepção.

## 12. Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py`.

- sentinel persistente;
- PID + identidade Linux;
- encerramento independente do planner;
- bloqueio de reinício até liberação consciente.

## 13. Diagnóstico e telemetria

Diagnóstico em `src/context_anchor/doctor.py`.

Telemetria estruturada em `src/context_anchor/runtime_log.py`:

- `runtime/logs/panel.log`;
- `runtime/logs/central.log`;
- `runtime/logs/robot.log`.

Credenciais não são registradas.

## 14. Gerenciamento de processos

Implementado em `src/context_anchor/process_registry.py`.

Registros guardam PID e tempo de início para evitar agir sobre PID reutilizado. Processos Linux em estado `Z` são tratados como desligados.

## 15. Acesso remoto — futuro

Antes de publicar Painel ou Central na Internet serão necessários TLS, autenticação forte, pareamento, revogação, rate limiting, proteção contra replay, auditoria e confirmação para ações sensíveis.

## 16. Canais — futuro

```text
Web remoto
WhatsApp
Telegram
Instagram
    ↓
Gateway de comandos
    ↓
Central
    ↓
Robô local
```

Nenhum adaptador de mensageria foi implementado ainda.

## 17. Princípio local-first

O controle físico permanece no Robô local. Painel, serviços externos e canais futuros enviam intenção e recebem resultado; nenhuma camada externa acessa diretamente mouse, teclado, câmera ou aplicativos sem passar pelo Robô e pela Policy Layer.