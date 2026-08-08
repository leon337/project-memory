# Context Anchor Operator

MVP de um operador digital local que recebe comandos por uma interface Web, entrega a tarefa a um agente no computador, executa uma ação permitida no navegador e devolve o resultado verificado.

## Escopo desta versão

Esta primeira versão implementa o teste vertical:

```text
Web
  ↓
Control Plane (FastAPI)
  ↓
Fila durável (SQLite)
  ↓
Agente local autenticado
  ↓
Planner + Policy
  ↓
Playwright / Chromium
  ↓
Verificação do resultado
  ↓
Painel Web
```

Comandos suportados:

- `abrir example.com`
- `abrir https://www.python.org`
- `pesquisar agentes de IA`
- `buscar FastAPI`

Ações fora dessa allowlist são recusadas. Endereços `localhost`, `.local`, IPs privados, loopback e esquemas diferentes de HTTP/HTTPS também são bloqueados nesta versão.

## Requisitos

- Python 3.11 ou superior;
- sistema desktop Linux para o primeiro alvo operacional;
- Chromium instalado pelo Playwright.

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

Gere dois tokens diferentes e longos. Exemplo usando Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32)); print(secrets.token_urlsafe(32))"
```

Coloque os valores em:

```env
CONTEXT_ANCHOR_USER_TOKEN=...
CONTEXT_ANCHOR_AGENT_TOKEN=...
```

Não faça commit do arquivo `.env`.

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

Informe o token do usuário e envie, por exemplo:

```text
pesquisar FastAPI agentes
```

O painel acompanha a tarefa até `succeeded` ou `failed` e mostra o resultado retornado pelo agente.

## Testes

```bash
pytest
```

## Segurança atual

- o servidor escuta apenas `127.0.0.1` por padrão;
- usuário e agente usam tokens separados;
- os tokens não são armazenados no painel;
- o repositório não contém credenciais;
- o agente só executa ações previstas pela política do MVP;
- não existe execução arbitrária de shell;
- não existe bypass de login, MFA ou controles do sistema operacional.

Esta versão ainda não deve ser exposta diretamente à Internet. A operação remota será adicionada depois de autenticação mais forte, TLS, pareamento de dispositivo, rate limiting e política de confirmação para ações sensíveis.

## Próximas capacidades

Depois de validar este teste vertical:

1. percepção de tela e árvore de acessibilidade;
2. controle de mouse/teclado e aplicativos com política explícita;
3. planner por modelo de IA com saída estruturada;
4. confirmação humana para ações sensíveis;
5. Control Plane remoto com autenticação forte;
6. adaptadores Telegram, WhatsApp e Instagram.

O estado e as decisões do projeto são mantidos em `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` e `docs/NEXT.md`.
