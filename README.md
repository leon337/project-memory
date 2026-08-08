# Robô Operador — MVP 0.3

Operador digital local com **Painel do Robô**, Central, fila de tarefas e Robô executor.

## Visão simples

```text
Você
  ↓
Painel do Robô
  ↓
Central
  ↓
Fila SQLite
  ↓
Robô local
  ↓
Planner + Policy Layer
  ├─ Navegador: Playwright / Chromium
  └─ Desktop: PyAutoGUI / Linux X11
  ↓
Resultado volta ao Painel
```

## Comandos principais

Com a `.venv` ativa:

```bash
painel-robo
```

Abre o **Painel do Robô** em:

```text
http://127.0.0.1:8765
```

O Painel é a interface principal para operação e aprendizado.

Também continuam disponíveis:

```bash
central
robo
diagnostico-robo
parar-robo status
```

## O que o Painel do Robô já faz

- mostra se Central e Robô estão ligados;
- mostra se o controle do Desktop está habilitado;
- mostra o estado da parada de emergência;
- liga e para a Central quando ela está registrada pela versão atual;
- liga, para e reinicia o Robô;
- altera visualmente `CONTEXT_ANCHOR_DESKTOP_ENABLED`;
- executa diagnóstico de leitura;
- mostra tarefas recentes;
- envia tarefas para o Robô sem exigir que o token seja digitado no navegador;
- mostra logs dos processos iniciados pelo Painel;
- possui Laboratório de comandos guiados.

O Laboratório explica comandos de desenvolvimento antes da execução manual. Ele não oferece shell remoto arbitrário.

## Navegador

Comandos atuais:

- `abrir example.com`
- `abrir https://www.python.org`
- `pesquisar agentes de IA`
- `buscar FastAPI`

Localhost, `.local`, IPs privados/loopback e esquemas diferentes de HTTP/HTTPS permanecem bloqueados.

## Desktop

Ações tipadas em código:

- `capturar tela`
- `janela ativa`
- `mover mouse 120 350`
- `clicar`
- `clicar direito`
- `digitar algum texto`
- `tecla enter`
- `abrir aplicativo firefox`

Aplicativos da allowlist inicial:

- Firefox;
- Chromium/Chrome;
- Nemo/Nautilus;
- Xed/Gedit;
- VS Code;
- calculadora;
- LibreOffice.

Aplicativos usam `shell=False`; não existe executor genérico de shell remoto.

## Requisitos

- Python 3.11+;
- Linux desktop para o primeiro alvo;
- sessão X11 para o backend físico inicial;
- Chromium do Playwright;
- `xdotool` e `scrot` para os primeiros recursos de percepção.

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
```

## Configuração inicial

```bash
cp .env.example .env
```

Gere dois tokens diferentes:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32)); print(secrets.token_urlsafe(32))"
```

Configure:

```env
CONTEXT_ANCHOR_USER_TOKEN=...
CONTEXT_ANCHOR_AGENT_TOKEN=...
```

O Desktop começa desligado por padrão:

```env
CONTEXT_ANCHOR_DESKTOP_ENABLED=false
```

No MVP 0.3 essa opção também pode ser alterada pelo Painel do Robô.

## Fluxo recomendado de uso

Depois da instalação:

```bash
source .venv/bin/activate
painel-robo
```

Abra:

```text
http://127.0.0.1:8765
```

A partir daí use os botões do Painel para ligar Central e Robô, consultar diagnóstico e enviar tarefas.

Se uma Central de uma versão anterior já estiver rodando sem registro de PID, o Painel pode detectá-la como online, mas pedirá que ela seja parada manualmente uma vez. Depois de reiniciada pela versão nova, passa a ser gerenciável pelo Painel.

## Laboratório de aprendizado

O Painel possui uma área para colar linhas como:

```text
git pull
pip install -e .
source .venv/bin/activate
central
robo
diagnostico-robo
```

Para comandos catalogados, o Painel mostra:

- o que o comando faz;
- por que ele está sendo usado;
- qual resultado esperar;
- onde deve ser executado.

Comandos desconhecidos não são executados automaticamente.

## Parada de emergência

Pelo terminal:

```bash
parar-robo status
parar-robo trigger --reason "parada manual"
parar-robo clear
```

O Painel também oferece botões para ativar e liberar a emergência.

Enquanto o marcador persistente estiver ativo, o Robô recusa reinício.

## Recuperação de tarefas

Cada tarefa reivindicada pelo Robô recebe um lease temporário e um token de propriedade.

- lease padrão: 120 segundos;
- máximo padrão: 3 tentativas;
- resultado com lease antigo é recusado;
- tarefa abandonada pode voltar para a fila;
- após interrupções repetidas, a tarefa falha para evitar loop infinito.

## Testes

```bash
pytest
```

O GitHub Actions compila e testa Central, fila, leases, desktop, política, planner, parada de emergência e Painel sem exigir uma sessão gráfica real.

## Segurança atual

- Painel: `127.0.0.1:8765` por padrão;
- Central: `127.0.0.1:8000` por padrão;
- tokens separados para usuário e Robô;
- `.env` fora do Git;
- desktop sujeito a feature gate e Policy Layer;
- aplicativos por allowlist;
- sem shell remoto arbitrário;
- sem bypass de login/MFA;
- parada de emergência independente do planner;
- processos são identificados por PID + tempo de início antes de encerramento pelo Painel.

Esta versão não deve ser exposta diretamente à Internet.

## Próximos passos

1. validar fisicamente o Painel do Robô no Linux real;
2. validar screenshot, janela ativa, mouse, teclado, aplicativos e emergência pelo Painel;
3. integrar o primeiro planner por IA estruturado;
4. depois avançar para acesso remoto seguro e Telegram/WhatsApp/Instagram.

O estado oficial do projeto é mantido em `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` e `docs/NEXT.md`.
