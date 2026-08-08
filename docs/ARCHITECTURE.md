# ARCHITECTURE

## Terminologia usada

Para facilitar operação e aprendizado:

- **Central** = nome de uso para o processo técnico `Control Plane`;
- **Robô local** = nome de uso para o processo técnico `local agent`;
- **Painel Web** = interface em `http://127.0.0.1:8000` usada para enviar tarefas à Central;
- **Painel do Robô** = gerenciador local planejado para operar, configurar, diagnosticar e ensinar o funcionamento do sistema.

Os nomes técnicos permanecem no código porque descrevem papéis arquiteturais, mas a interface humana usa os nomes intuitivos.

## Estado arquitetural atual

```text
Usuário
  ↓
Painel Web local
  ↓
Central (Control Plane / FastAPI)
  ↓
SQLite — fila, histórico e leases
  ↓
HTTP polling autenticado
  ↓
Robô local (local agent)
  ↓
Planner
  ├─ Determinístico ativo
  └─ Contrato estruturado para provedor futuro
  ↓
Policy Layer
  ├─ Browser policy
  └─ Desktop policy + feature gate local
  ↓
Executores
  ├─ Playwright / Chromium
  └─ PyAutoGUI / Linux desktop
  ↓
Verificação do resultado
  ↓
Central
```

O controle físico permanece local. A Central envia intenções/tarefas; o Robô local decide, pela Policy Layer, se a ação tipada pode ser executada.

## Arquitetura planejada do Painel do Robô

O Painel do Robô será um processo local separado da Central e do Robô.

```text
                  Painel do Robô
               operação + aprendizado
                /        |        \
               /         |         \
          Central      Robô      Configuração
             |           |            |
          tarefas     execução      capacidades
             \           |            /
              \          |           /
               logs + diagnóstico + testes
```

A separação é intencional: o painel precisa continuar disponível para religar ou diagnosticar a Central e o Robô quando qualquer um deles estiver parado.

Responsabilidades planejadas:

- detectar se Central e Robô estão ligados;
- iniciar, parar e reiniciar esses processos locais;
- mostrar estado das capacidades habilitadas;
- alterar somente configurações explicitamente suportadas;
- executar diagnóstico;
- apresentar logs por componente;
- mostrar histórico e estado das tarefas;
- oferecer testes guiados;
- explicar comandos e resultados esperados em linguagem simples;
- oferecer uma área de comandos de manutenção controlados para o modo de desenvolvimento.

O painel não será um terminal remoto de shell arbitrário. Comandos de manutenção executáveis pelo painel terão um catálogo explícito. Outros comandos poderão ser exibidos com explicação para execução manual.

## 1. Central

Implementada tecnicamente em `src/context_anchor/control_plane.py`.

Responsabilidades:

- servir o Painel Web;
- autenticar o usuário;
- autenticar o Robô local com credencial separada;
- criar e consultar tarefas;
- entregar tarefas ao Robô;
- emitir lease por execução;
- receber resultado protegido pelo token do lease.

Por padrão escuta apenas `127.0.0.1`.

Comando humano principal:

```text
central
```

Alias técnico preservado: `context-anchor-control`.

## 2. Persistência e leases

Implementada em `src/context_anchor/store.py` com SQLite.

Fluxo:

```text
queued
  ↓ claim + lease
running
  ↓
succeeded | failed
```

Se um lease expirar antes da conclusão, a tarefa pode voltar a `queued`. Depois do limite de tentativas, ela passa a `failed`.

Cada claim gera um `lease_token` novo. Um resultado só é aceito se o token ainda pertencer à execução atual, impedindo que uma execução atrasada finalize uma tarefa já retomada.

## 3. Robô local

Implementado tecnicamente em `src/context_anchor/local_agent.py`.

Fluxo atual:

1. verifica parada de emergência;
2. registra sua identidade de processo local;
3. autentica na Central;
4. reivindica uma tarefa e seu lease;
5. pede um plano ao planner ativo;
6. passa o plano pela Policy Layer;
7. executa a ação autorizada;
8. verifica o resultado;
9. devolve resultado junto ao lease da execução.

Comando humano principal:

```text
robo
```

Alias técnico preservado: `context-anchor-agent`.

## 4. Planner

O contrato está em `src/context_anchor/planner.py`.

Existem hoje:

- `DeterministicPlanner`, ativo;
- `StructuredAction`, esquema fechado para ações conhecidas;
- `ProviderPlanner`, adaptador para um provedor futuro;
- `StructuredPlanProvider`, protocolo de integração.

O contrato não possui campo para shell, código, caminho de executável livre ou credenciais.

Mesmo uma saída estruturalmente válida ainda precisa ser autorizada pela Policy Layer.

## 5. Policy Layer

Implementada em `src/context_anchor/policy.py`.

### Navegador

- apenas HTTP/HTTPS;
- bloqueio de localhost, `.local`, IPs privados, loopback, link-local e reservados.

### Desktop

- desktop desativado por padrão;
- ações precisam pertencer à allowlist tipada;
- coordenadas possuem validação;
- texto limitado a 500 caracteres e sem quebra de linha dentro da mesma ação;
- teclas aceitas pertencem a allowlist específica;
- aplicativos pertencem a allowlist fixa.

## 6. Navegador

Implementado em `src/context_anchor/actions.py` com Playwright/Chromium.

Verificação atual:

- URL solicitada;
- URL final;
- título;
- status HTTP;
- `verified`.

Preferência arquitetural:

```text
API/DOM
→ automação estruturada
→ acessibilidade
→ visão + mouse/teclado como fallback
```

## 7. Ações de desktop

Backend físico em `src/context_anchor/desktop.py`.

Capacidades atuais:

- screenshot;
- janela ativa via `xdotool`;
- mover mouse;
- clique esquerdo/direito;
- digitar texto;
- pressionar teclas permitidas;
- abrir aplicativos permitidos.

PyAutoGUI é importado de forma lazy para que processos de servidor e CI não exijam sessão gráfica apenas para importar o pacote.

O backend inicial considera Linux/X11. Wayland permanece não validado.

## 8. Registro de aplicativos

O Robô não aceita nome de executável arbitrário.

O registro interno mapeia ids estáveis para executáveis conhecidos, como Firefox, Chromium, Nemo/Nautilus, Xed/Gedit, VS Code, calculadora e LibreOffice.

A abertura usa `subprocess.Popen` com `shell=False`.

## 9. Percepção

Primeiro slice implementado:

- screenshot;
- metadado de janela ativa quando `xdotool` está disponível.

Ainda faltam:

- árvore de acessibilidade;
- percepção semântica da tela;
- DOM compartilhado como contexto para planner;
- fusão de múltiplas fontes de percepção.

## 10. Parada de emergência

Implementada em `src/context_anchor/emergency_stop.py`.

Mecanismos:

- sentinel persistente em arquivo;
- PID do Robô acompanhado do tempo de início do processo Linux;
- verificação contra reutilização de PID;
- `SIGTERM` direto ao processo local quando a identidade confere;
- Robô recusa reinício enquanto o sentinel existir;
- configuração da parada não depende das credenciais do Robô.

Comando humano principal: `parar-robo`.

Alias técnico preservado: `context-anchor-stop`.

## 11. Diagnóstico local

`src/context_anchor/doctor.py` apenas observa o ambiente e informa dependências e sessão gráfica; não executa ações físicas.

Comando humano principal: `diagnostico-robo`.

Alias técnico preservado: `context-anchor-doctor`.

## 12. Credenciais

Credenciais não devem aparecer:

- no código;
- nos prompts;
- nos logs;
- no Git;
- diretamente no modelo.

`.env` permanece fora do repositório. Usuário e Robô possuem tokens separados.

## 13. Central remota — planejada

Antes de exposição à Internet ainda são necessários:

- TLS;
- autenticação forte;
- pareamento de dispositivo;
- revogação/rotação;
- rate limiting;
- proteção contra replay;
- auditoria adequada;
- confirmação humana para ações sensíveis.

## 14. Adaptadores de canais — planejados

Arquitetura-alvo:

```text
Web
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

## 15. Princípio local-first

Serviços externos poderão enviar objetivos e receber resultados, mas não terão acesso direto ao mouse, teclado, câmera ou aplicativos. Toda ação física deverá passar pelo Robô local, pelo feature gate e pela Policy Layer.
