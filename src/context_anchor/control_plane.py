from __future__ import annotations

import secrets
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse

from .config import ControlPlaneSettings
from .schemas import AgentResult, AgentTask, TaskCreate, TaskView
from .store import TaskStore

INDEX_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Central do Robô</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 820px; margin: 40px auto; padding: 0 16px; }
    input, button { box-sizing: border-box; width: 100%; padding: 12px; margin: 6px 0; }
    pre { white-space: pre-wrap; background: #f4f4f4; padding: 12px; border-radius: 8px; }
    small { color: #555; }
    details { margin: 16px 0; padding: 12px; border: 1px solid #ddd; border-radius: 8px; }
    code { background: #f4f4f4; padding: 2px 5px; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Central do Robô — MVP 0.2</h1>
  <p>A Central recebe seus comandos e entrega as tarefas ao Robô local, que executa apenas ações permitidas.</p>
  <details>
    <summary>Comandos disponíveis</summary>
    <p><strong>Navegador:</strong> <code>abrir example.com</code>, <code>pesquisar inteligência artificial</code>.</p>
    <p><strong>Desktop:</strong> <code>capturar tela</code>, <code>janela ativa</code>, <code>mover mouse 120 350</code>, <code>clicar</code>, <code>clicar direito</code>, <code>digitar texto</code>, <code>tecla enter</code>, <code>abrir aplicativo firefox</code>.</p>
    <small>Se CONTEXT_ANCHOR_DESKTOP_ENABLED=false, as ações físicas serão recusadas pelo Robô local.</small>
  </details>
  <label>Token do usuário</label>
  <input id="token" type="password" autocomplete="off" placeholder="Token configurado na Central" />
  <label>Comando</label>
  <input id="command" placeholder="pesquisar FastAPI" />
  <button id="send">Executar</button>
  <small>O token não é salvo pelo painel.</small>
  <pre id="output">Aguardando comando.</pre>
<script>
const output = document.getElementById('output');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function api(path, token, options = {}) {
  const headers = Object.assign({}, options.headers || {}, {Authorization: `Bearer ${token}`});
  const response = await fetch(path, Object.assign({}, options, {headers}));
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.status === 204 ? null : response.json();
}

document.getElementById('send').onclick = async () => {
  const token = document.getElementById('token').value.trim();
  const command = document.getElementById('command').value.trim();
  if (!token || !command) return;
  try {
    output.textContent = 'Enviando tarefa...';
    const task = await api('/api/tasks', token, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({command})
    });
    output.textContent = JSON.stringify(task, null, 2);
    while (task.status === 'queued' || task.status === 'running') {
      await sleep(1200);
      const current = await api(`/api/tasks/${task.id}`, token);
      Object.assign(task, current);
      output.textContent = JSON.stringify(task, null, 2);
    }
  } catch (error) {
    output.textContent = String(error);
  }
};
</script>
</body>
</html>
"""


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente.")
    return authorization.removeprefix("Bearer ").strip()


def create_app(settings: ControlPlaneSettings | None = None) -> FastAPI:
    cfg = settings or ControlPlaneSettings()
    store = TaskStore(cfg.db_path)
    app = FastAPI(title="Central do Robô", version="0.2.0")

    def require_user(authorization: Annotated[str | None, Header()] = None) -> None:
        token = _bearer_token(authorization)
        if not secrets.compare_digest(token, cfg.user_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    def require_agent(authorization: Annotated[str | None, Header()] = None) -> None:
        token = _bearer_token(authorization)
        if not secrets.compare_digest(token, cfg.agent_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/tasks", response_model=TaskView, dependencies=[Depends(require_user)])
    def create_task(payload: TaskCreate) -> dict:
        return store.create_task(payload.command)

    @app.get("/api/tasks/{task_id}", response_model=TaskView, dependencies=[Depends(require_user)])
    def get_task(task_id: str) -> dict:
        task = store.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarefa não encontrada.")
        return task

    @app.get("/api/agent/next", dependencies=[Depends(require_agent)], response_model=None)
    def next_task(agent_id: Annotated[str, Query(min_length=1, max_length=100)]):
        task = store.claim_next(
            agent_id,
            lease_seconds=cfg.task_lease_seconds,
            max_attempts=cfg.task_max_attempts,
        )
        if task is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        return AgentTask(
            id=task["id"],
            command=task["command"],
            lease_token=task["lease_token"],
        )

    @app.post("/api/agent/tasks/{task_id}/result", response_model=TaskView, dependencies=[Depends(require_agent)])
    def finish_task(task_id: str, payload: AgentResult) -> dict:
        updated = store.complete_task(
            task_id,
            lease_token=payload.lease_token,
            ok=payload.ok,
            result=payload.result,
            error=payload.error,
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Lease da tarefa expirou ou não pertence mais a esta execução.",
            )
        return updated

    return app


def main() -> None:
    cfg = ControlPlaneSettings()
    uvicorn.run(create_app(cfg), host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
