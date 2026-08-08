# Context Anchor Operator

Operador digital local controlado por uma interface Web. O sistema recebe uma tarefa, entrega ao agente no computador, aplica uma política local, executa apenas ações tipadas permitidas e devolve o resultado verificado.

## Estado atual

O projeto já possui dois slices operacionais:

```text
Web
  ↓
Control Plane (FastAPI)
  ↓
Fila durável (SQLite)
  ↓
Agente local autenticado
  ↓
Planner determinístico + Policy Layer
  ├─→ Playwright / Chromium
  └─→ Desktop Linux / PyAutoGUI
        ↓
     verificação
        ↓
     Painel Web
```

### Navegador

Comandos suportados:

- `abrir example.com`
- `abrir https://www.python.org`
- `pesquisar agentes de IA`
- `buscar FastAPI`

Endereços `localhost`, `.local`, IPs privados, loopback e esquemas diferentes de HTTP/HTTPS permanecem bloqueados.

### Desktop

O controle de desktop existe no código, mas fica **desativado por padrão** até ser habilitado localmente.

Comandos tipados atuais:

- `capturar tela`
- `janela ativa`
- `mover mouse 120 350`
- `clicar`
- `clicar direito`
- `digitar algum texto`
- `tecla enter`
- `abrir aplicativo firefox`

Aplicativos aceitos pela allowlist atual:

- `firefox`
- `chromium`
- `arquivos` — Nemo ou Nautilus;
- `editor` — Xed ou Gedit;
- `vscode`;
- `calculadora`;
- `libreoffice`.

Não existe execução arbitrária de shell. O nome de aplicativo recebido remotamente nunca vira um comando livre: ele precisa corresponder à allowlist fixa e é iniciado com `shell=False`.

A digitação é limitada a 500 caracteres por ação, quebras de linha exigem uma ação de tecla separada e atalhos arbitrários ainda não são aceitos.

## Requisitos

- Python 3.11 ou superior;
- Linux desktop para o primeiro alvo operacional;
- Chromium instalado pelo Playwright;
- sessão gráfica X11 para o backend PyAutoGUI inicial.

Para a percepção de janela ativa no Linux, instale `xdotool`. Em Linux Mint/Ubuntu:

```bash
sudo apt update
sudo apt install -y xdotool scrot
```

O suporte Wayland ainda não foi validado.

## Instalação

```bash
git clone https://github.com/leon337/project-memory.git
cd project-memory
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m playwright install chromium
```

## Configuração

Copie o exemplo:

```bash
cp .env.example .env
```

Gere dois tokens diferentes e longos:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32)); print(secrets.token_urlsafe(32))"
```

Coloque os valores em:

```env
CONTEXT_ANCHOR_USER_TOKEN=...
CONTEXT_ANCHOR_AGENT_TOKEN=...
```

Não faça commit do arquivo `.env`.

O controle físico do desktop permanece desligado inicialmente:

```env
CONTEXT_ANCHOR_DESKTOP_ENABLED=false
```

Somente depois do teste local, altere para:

```env
CONTEXT_ANCHOR_DESKTOP_ENABLED=true
```

## Executar

Terminal 1 — Control Plane:

```bash
python -m context_anchor.control_plane
```

Terminal 2 — agente local:

```bash
python -m context_anchor.local_agent
```

Abra no navegador:

```text
http://127.0.0.1:8000
```

Informe o token do usuário e envie uma tarefa.

## Emergency stop local

O projeto possui um mecanismo de parada separado do planner/modelo.

Status:

```bash
context-anchor-stop status
```

Parar o agente imediatamente:

```bash
context-anchor-stop trigger --reason "parada manual"
```

O comando grava `runtime/EMERGENCY_STOP` e tenta enviar `SIGTERM` diretamente ao PID registrado pelo agente local.

Enquanto o arquivo de parada existir, o agente se recusa a iniciar novamente. Para liberar conscientemente uma nova execução:

```bash
context-anchor-stop clear
```

O `FAILSAFE` do PyAutoGUI também permanece habilitado como proteção adicional local.

## Testes

```bash
pytest
```

O CI não depende de uma sessão gráfica para testar a lógica de desktop: os testes usam um backend falso para verificar roteamento, políticas e emergency stop. O backend físico ainda precisa ser validado em um desktop Linux real.

## Segurança atual

- o servidor escuta apenas `127.0.0.1` por padrão;
- usuário e agente usam tokens separados;
- tokens não são armazenados no painel;
- o repositório não contém credenciais;
- desktop control fica desligado por padrão;
- ações de desktop passam pela Policy Layer;
- aplicativos usam allowlist fixa;
- não existe shell arbitrário;
- não existe bypass de login, MFA ou controles do sistema operacional;
- emergency stop persiste entre reinicializações do agente até ser limpo localmente.

Esta versão ainda não deve ser exposta diretamente à Internet. A operação remota será adicionada apenas depois de autenticação mais forte, TLS, pareamento de dispositivo, rate limiting e política de confirmação para ações sensíveis.

## Próximas capacidades

1. validar navegador e desktop no computador Linux real;
2. melhorar percepção estruturada da tela/janelas e compatibilidade Linux;
3. integrar planner por modelo de IA com saída estruturada;
4. adicionar confirmação humana para ações sensíveis;
5. publicar Control Plane com autenticação forte;
6. adicionar adaptadores Telegram, WhatsApp e Instagram.

O estado e as decisões do projeto são mantidos em `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` e `docs/NEXT.md`.
