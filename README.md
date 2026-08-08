# Robô Operador — MVP 0.2

Operador digital local controlado por uma interface Web.

Para facilitar o aprendizado, os nomes usados no dia a dia são simples:

- **Central**: recebe e organiza as tarefas;
- **Robô local**: busca e executa as tarefas no computador;
- **Painel Web**: lugar onde o usuário digita os comandos.

Os nomes técnicos internos continuam existindo no código: `Control Plane` corresponde à Central e `local agent` corresponde ao Robô local.

## Como o sistema funciona

```text
Usuário
  ↓
Painel Web
  ↓
Central (FastAPI)
  ↓
Fila de tarefas (SQLite + leases)
  ↓
Robô local
  ↓
Planner + Policy Layer
  ├─→ Navegador: Playwright / Chromium
  └─→ Desktop: PyAutoGUI / Linux
        ↓
     resultado
        ↓
     Central / Painel Web
```

## Comandos para ligar e diagnosticar

Com o ambiente virtual ativo:

```bash
central
```

Liga a **Central**.

```bash
robo
```

Liga o **Robô local**.

```bash
diagnostico-robo
```

Verifica o ambiente do computador sem clicar, digitar ou abrir aplicativos.

```bash
parar-robo status
parar-robo trigger --reason "parada manual"
parar-robo clear
```

Consulta, aciona e limpa a parada de emergência.

Os comandos técnicos antigos continuam funcionando por compatibilidade:

```text
context-anchor-control
context-anchor-agent
context-anchor-stop
context-anchor-doctor
```

## Navegador

Comandos suportados:

- `abrir example.com`
- `abrir https://www.python.org`
- `pesquisar agentes de IA`
- `buscar FastAPI`

Endereços `localhost`, `.local`, IPs privados, loopback e esquemas diferentes de HTTP/HTTPS permanecem bloqueados.

## Desktop

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

Não existe execução arbitrária de shell. O nome de aplicativo recebido remotamente precisa corresponder à allowlist fixa e é iniciado com `shell=False`.

A digitação é limitada a 500 caracteres por ação, quebras de linha exigem uma ação de tecla separada e atalhos arbitrários ainda não são aceitos.

## Requisitos

- Python 3.11 ou superior;
- Linux desktop para o primeiro alvo operacional;
- Chromium instalado pelo Playwright;
- sessão gráfica X11 para o backend PyAutoGUI inicial.

Para percepção de janela ativa e screenshot em Linux Mint/Ubuntu:

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

O controle físico do desktop permanece desligado inicialmente:

```env
CONTEXT_ANCHOR_DESKTOP_ENABLED=false
```

Somente depois do teste local, altere para:

```env
CONTEXT_ANCHOR_DESKTOP_ENABLED=true
```

## Diagnóstico local

Antes de habilitar o desktop, execute:

```bash
diagnostico-robo
```

O diagnóstico verifica sem realizar nenhuma ação física:

- versão do Python;
- tipo de sessão gráfica;
- presença de `DISPLAY`/Wayland;
- instalação do PyAutoGUI;
- `xdotool` e `scrot`;
- aplicativos da allowlist instalados.

## Executar

Terminal da **Central**:

```bash
central
```

Terminal do **Robô local**:

```bash
robo
```

Abra no navegador:

```text
http://127.0.0.1:8000
```

Informe o token do usuário e envie uma tarefa.

## Recuperação de tarefas interrompidas

Cada tarefa reivindicada pelo Robô recebe um lease temporário e um token de propriedade.

- lease padrão: 120 segundos;
- máximo padrão: 3 tentativas;
- resultado com lease antigo é recusado;
- tarefa cujo Robô desapareceu volta para a fila quando o lease expira;
- após interrupções repetidas, a tarefa é marcada como `failed` para evitar loop infinito.

## Parada de emergência

Status:

```bash
parar-robo status
```

Parar o Robô imediatamente:

```bash
parar-robo trigger --reason "parada manual"
```

Enquanto o marcador de parada existir, o Robô se recusa a iniciar novamente. Para liberar uma nova execução:

```bash
parar-robo clear
```

O `FAILSAFE` do PyAutoGUI também permanece habilitado como proteção adicional local.

## Testes

```bash
pytest
```

O CI não depende de uma sessão gráfica para testar a lógica de desktop: os testes usam um backend falso para verificar roteamento, políticas, leases e parada de emergência.

## Segurança atual

- a Central escuta apenas `127.0.0.1` por padrão;
- usuário e Robô usam tokens separados;
- tokens não são armazenados no painel;
- o repositório não contém credenciais;
- controle de desktop fica desligado por padrão;
- ações de desktop passam pela Policy Layer;
- aplicativos usam allowlist fixa;
- não existe shell arbitrário;
- não existe bypass de login, MFA ou controles do sistema operacional;
- parada de emergência persiste até ser limpa localmente;
- leases impedem resultados atrasados e recuperam tarefas interrompidas.

Esta versão ainda não deve ser exposta diretamente à Internet.

## Próximas capacidades

1. concluir a validação física do desktop;
2. melhorar percepção estruturada da tela e janelas;
3. integrar planner por modelo de IA com saída estruturada;
4. adicionar confirmação humana para ações sensíveis;
5. publicar a Central com autenticação forte;
6. adicionar Telegram, WhatsApp e Instagram.

O estado e as decisões do projeto são mantidos em `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` e `docs/NEXT.md`.
