from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import (
    ControlPlaneSettings,
    DashboardSettings,
    DesktopSettings,
    EmergencyStopSettings,
    LocalAgentSettings,
)
from .conversation import ConversationBackend, ProjectConversationService
from .dashboard_ui import INDEX_HTML
from .doctor import collect_diagnostics
from .emergency_stop import EmergencyStop
from .process_registry import record_is_alive, terminate_registered_process
from .redaction import redact_exception
from .runtime_log import tail_runtime_log, write_runtime_log
from .store import TaskStore


GUIDED_COMMANDS: dict[str, dict[str, str]] = {
    "git pull": {
        "what": "Baixa do GitHub as mudanças mais recentes do projeto e atualiza sua cópia local.",
        "why": "Usamos quando o código no GitHub mudou e o computador precisa receber a versão nova.",
        "expected": "Pode aparecer 'Already up to date' ou 'Fast-forward' com a lista de arquivos alterados.",
        "where": "Terminal, dentro da pasta do projeto.",
    },
    "pip install -e .": {
        "what": "Atualiza a instalação editável do projeto dentro do ambiente virtual Python.",
        "why": "É necessário quando mudamos comandos ou arquivos Python e queremos que a .venv use a versão nova.",
        "expected": "No final deve aparecer uma mensagem de instalação concluída com sucesso.",
        "where": "Terminal, dentro do projeto e com (.venv) ativo.",
    },
    "source .venv/bin/activate": {
        "what": "Ativa o ambiente virtual Python do projeto no terminal atual.",
        "why": "Faz o terminal usar o Python e os programas instalados especificamente para este projeto.",
        "expected": "O texto '(.venv)' aparece no começo do prompt.",
        "where": "Terminal, dentro da pasta do projeto.",
    },
    "central": {
        "what": "Liga a Central, o serviço que recebe tarefas e mantém a fila do Robô.",
        "why": "Sem a Central, o painel de tarefas e o Robô não conseguem trocar trabalho.",
        "expected": "A Central passa a responder em http://127.0.0.1:8000.",
        "where": "Pode ser feito pelo terminal ou pelo controle da Central neste Painel.",
    },
    "robo": {
        "what": "Liga o Robô local, que busca tarefas na Central e executa ações permitidas.",
        "why": "A Central organiza; o Robô é quem realmente executa navegador e desktop.",
        "expected": "O estado do Robô muda para Ligado e ele começa a consultar a fila.",
        "where": "Pode ser feito pelo terminal ou pelo controle do Robô neste Painel.",
    },
    "diagnostico-robo": {
        "what": "Verifica Python, sessão gráfica, Playwright, PyAutoGUI, xdotool, scrot e aplicativos disponíveis.",
        "why": "Ajuda a descobrir problemas antes de mandar o Robô controlar o computador.",
        "expected": "Um relatório com o estado das dependências, sem clicar nem digitar nada.",
        "where": "Terminal ou botão Diagnóstico deste Painel.",
    },
    "parar-robo status": {
        "what": "Mostra se a parada de emergência está ativa.",
        "why": "Confirma se o Robô está bloqueado por segurança antes de tentar iniciá-lo.",
        "expected": "Um estado indicando active: true ou false.",
        "where": "Terminal ou controle Emergência deste Painel.",
    },
}


class DesktopToggle(BaseModel):
    enabled: bool


class TaskRequest(BaseModel):
    command: str = Field(min_length=1, max_length=500)


class ConversationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)


class GuidedRequest(BaseModel):
    command: str = Field(min_length=1, max_length=500)


class DashboardControl(Protocol):
    def status(self) -> dict[str, Any]: ...
    def diagnostics(self) -> dict[str, Any]: ...
    def start_central(self) -> dict[str, Any]: ...
    def stop_central(self) -> dict[str, Any]: ...
    def start_robot(self) -> dict[str, Any]: ...
    def stop_robot(self) -> dict[str, Any]: ...
    def restart_robot(self) -> dict[str, Any]: ...
    def set_desktop_enabled(self, enabled: bool) -> dict[str, Any]: ...
    def trigger_emergency(self) -> dict[str, Any]: ...
    def clear_emergency(self) -> dict[str, Any]: ...
    def submit_task(self, command: str) -> dict[str, Any]: ...
    def explain_guided_command(self, command: str) -> dict[str, Any]: ...


class DashboardController:
    def __init__(
        self,
        *,
        control_settings: ControlPlaneSettings | None = None,
        dashboard_settings: DashboardSettings | None = None,
        emergency_settings: EmergencyStopSettings | None = None,
        project_root: Path | str | None = None,
    ) -> None:
        self.control = control_settings or ControlPlaneSettings()
        self.dashboard = dashboard_settings or DashboardSettings()
        self.emergency_cfg = emergency_settings or EmergencyStopSettings()
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.store = TaskStore(self.control.db_path)
        self.stop = EmergencyStop(
            self.emergency_cfg.emergency_stop_path,
            self.emergency_cfg.agent_pid_path,
        )

    @property
    def _log_dir(self) -> Path:
        return self.project_root / self.dashboard.log_dir

    def _log(self, message: str, *, level: str = "INFO") -> None:
        write_runtime_log("panel", message, level=level, log_dir=self._log_dir)

    def _central_url(self) -> str:
        return f"http://{self.control.host}:{self.control.port}"

    def _central_online(self) -> bool:
        try:
            response = httpx.get(f"{self._central_url()}/health", timeout=0.6)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def _robot_online(self) -> bool:
        return record_is_alive(self.emergency_cfg.agent_pid_path)

    def _runtime_logs(self) -> dict[str, list[str]]:
        return {
            component: tail_runtime_log(component, lines=80, log_dir=self._log_dir)
            for component in ("panel", "central", "robot")
        }

    def _log_events(self, logs: dict[str, list[str]]) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []
        for component, lines in logs.items():
            for line in lines:
                first = line.split(" ", 1)[0] if line else ""
                timestamp = first if len(first) >= 19 and "T" in first else ""
                events.append({"component": component, "timestamp": timestamp, "line": line})
        events.sort(key=lambda event: (event["timestamp"] or "0000", event["component"]))
        return events[-160:]

    def _ai_status(self) -> dict[str, Any]:
        """Expose configuration availability without leaking credentials/models as usage."""

        try:
            cfg = LocalAgentSettings()
        except Exception:
            return {"available": False, "configured_providers": []}
        providers: list[str] = []
        if cfg.cloudflare_api_token and cfg.cloudflare_account_id:
            providers.append("cloudflare")
        if cfg.zai_api_key:
            providers.append("zai")
        if cfg.gemini_api_key:
            providers.append("gemini")
        return {"available": bool(providers), "configured_providers": providers}

    def status(self) -> dict[str, Any]:
        desktop = DesktopSettings()
        emergency = self.stop.status()
        logs = self._runtime_logs()
        return {
            "central": {
                "online": self._central_online(),
                "managed": record_is_alive(self.dashboard.central_pid_path),
            },
            "robot": {"online": self._robot_online()},
            "desktop": {"enabled": desktop.desktop_enabled},
            "emergency": emergency,
            "ai": self._ai_status(),
            "tasks": self.store.list_recent(limit=8),
            "logs": logs,
            "log_events": self._log_events(logs),
        }

    def diagnostics(self) -> dict[str, Any]:
        self._log("Diagnóstico solicitado pelo Painel")
        return collect_diagnostics()

    def _spawn(self, module: str, log_name: str) -> subprocess.Popen[bytes]:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        process_log = (self._log_dir / f"{log_name}-process.log").open("ab", buffering=0)
        return subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=self.project_root,
            stdout=process_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            shell=False,
        )

    def start_central(self) -> dict[str, Any]:
        if self._central_online():
            self._log("Pedido para ligar Central ignorado: já está online")
            return {"ok": True, "message": "A Central já está online."}
        self._log("Solicitado início da Central")
        process = self._spawn("context_anchor.control_plane", "central")
        for _ in range(25):
            if self._central_online():
                self._log(f"Central ligada pelo Painel pid={process.pid}")
                return {"ok": True, "message": "Central ligada.", "pid": process.pid}
            if process.poll() is not None:
                break
            time.sleep(0.12)
        self._log("Falha ao iniciar Central pelo Painel", level="ERROR")
        return {"ok": False, "message": "A Central não respondeu após a tentativa de início."}

    def stop_central(self) -> dict[str, Any]:
        self._log("Solicitada parada da Central")
        result = terminate_registered_process(self.dashboard.central_pid_path)
        if result["stopped"]:
            self._log("Sinal de parada enviado para a Central")
            return {"ok": True, "message": "Sinal de parada enviado para a Central.", **result}
        if self._central_online():
            self._log("Central online foi iniciada fora do Painel; parada recusada", level="WARN")
            return {
                "ok": False,
                "message": "A Central está online, mas foi iniciada fora do Painel. Pare-a no terminal uma vez e depois ligue-a pelo Painel.",
                **result,
            }
        return {"ok": True, "message": "A Central já está desligada.", **result}

    def start_robot(self) -> dict[str, Any]:
        if self.stop.is_triggered():
            self._log("Início do Robô recusado: emergência ativa", level="WARN")
            return {"ok": False, "message": "A parada de emergência está ativa. Limpe-a antes de ligar o Robô."}
        if self._robot_online():
            self._log("Pedido para ligar Robô ignorado: já está online")
            return {"ok": True, "message": "O Robô já está online."}
        if not self._central_online():
            self._log("Início do Robô recusado: Central desligada", level="WARN")
            return {"ok": False, "message": "Ligue a Central antes de ligar o Robô."}
        self._log("Solicitado início do Robô")
        process = self._spawn("context_anchor.local_agent", "robot")
        for _ in range(25):
            if self._robot_online():
                self._log(f"Robô ligado pelo Painel pid={process.pid}")
                return {"ok": True, "message": "Robô ligado.", "pid": process.pid}
            if process.poll() is not None:
                break
            time.sleep(0.12)
        self._log("Falha ao iniciar Robô pelo Painel", level="ERROR")
        return {"ok": False, "message": "O Robô não registrou seu processo após a tentativa de início."}

    def stop_robot(self) -> dict[str, Any]:
        self._log("Solicitada parada do Robô")
        result = terminate_registered_process(self.emergency_cfg.agent_pid_path)
        if result["stopped"]:
            self._log("Sinal de parada enviado para o Robô")
            return {"ok": True, "message": "Sinal de parada enviado para o Robô.", **result}
        return {"ok": True, "message": "O Robô já estava desligado ou o registro era antigo.", **result}

    def restart_robot(self) -> dict[str, Any]:
        self._log("Solicitado reinício do Robô")
        self.stop_robot()
        for _ in range(20):
            if not self._robot_online():
                break
            time.sleep(0.1)
        return self.start_robot()

    def set_desktop_enabled(self, enabled: bool) -> dict[str, Any]:
        env_path = self.project_root / self.dashboard.env_path
        if not env_path.exists():
            self._log("Falha ao alterar Desktop: arquivo .env não encontrado", level="ERROR")
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {env_path}")
        key = "CONTEXT_ANCHOR_DESKTOP_ENABLED"
        replacement = f"{key}={'true' if enabled else 'false'}"
        lines = env_path.read_text(encoding="utf-8").splitlines()
        changed = False
        updated: list[str] = []
        for line in lines:
            if line.startswith(f"{key}="):
                updated.append(replacement)
                changed = True
            else:
                updated.append(line)
        if not changed:
            updated.append(replacement)
        env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
        self._log(f"Desktop {'habilitado' if enabled else 'desabilitado'} pelo Painel")
        return {
            "ok": True,
            "enabled": enabled,
            "restart_required": self._robot_online(),
            "message": "Desktop habilitado." if enabled else "Desktop desabilitado.",
        }

    def trigger_emergency(self) -> dict[str, Any]:
        self._log("PARADA DE EMERGÊNCIA ativada pelo Painel", level="WARN")
        result = self.stop.trigger(reason="Painel do Robô", terminate_process=True)
        return {"ok": True, "message": "Parada de emergência ativada.", **result}

    def clear_emergency(self) -> dict[str, Any]:
        result = self.stop.clear()
        self._log("Parada de emergência liberada pelo Painel")
        return {"ok": True, "message": "Parada de emergência liberada.", **result}

    def submit_task(self, command: str) -> dict[str, Any]:
        if not self._central_online():
            self._log("Envio de tarefa recusado: Central desligada", level="WARN")
            raise RuntimeError("A Central está desligada.")
        response = httpx.post(
            f"{self._central_url()}/api/tasks",
            headers={"Authorization": f"Bearer {self.control.user_token}"},
            json={"command": command},
            timeout=4,
        )
        response.raise_for_status()
        task = response.json()
        self._log(
            f"Tarefa enviada pelo Painel id={task.get('id', 'desconhecido')} "
            f"status={task.get('status', 'desconhecido')}"
        )
        return task

    def explain_guided_command(self, command: str) -> dict[str, Any]:
        normalized = " ".join(command.strip().split())
        known = GUIDED_COMMANDS.get(normalized)
        if known:
            return {"known": True, "command": normalized, **known}
        return {
            "known": False,
            "command": normalized,
            "what": "Este comando ainda não faz parte do catálogo guiado do Painel.",
            "why": "O Painel não executa texto de terminal desconhecido automaticamente. Isso evita transformar a interface em shell remoto arbitrário.",
            "expected": "Você pode copiar o comando e revisar seu efeito antes de executá-lo manualmente.",
            "where": "Não será executado automaticamente nesta versão.",
        }


def _origin_is_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site", "").casefold()
    if not origin:
        return fetch_site not in {"cross-site"}
    if origin == "null":
        return False
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    request_host = request.headers.get("host", "")
    return parsed.netloc.casefold() == request_host.casefold()


def _default_conversation(active: DashboardControl) -> ConversationBackend:
    root = getattr(active, "project_root", Path.cwd())
    return ProjectConversationService(project_root=root)


def create_app(
    controller: DashboardControl | None = None,
    *,
    conversation: ConversationBackend | None = None,
) -> FastAPI:
    active = controller or DashboardController()
    chat = conversation or _default_conversation(active)
    app = FastAPI(title="Painel do Robô", version="0.4.1")
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
            if not _origin_is_allowed(request):
                return JSONResponse(status_code=403, content={"detail": "Origem não autorizada."})
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        return response

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return active.status()

    @app.get("/api/diagnostics")
    def diagnostics() -> dict[str, Any]:
        return active.diagnostics()

    @app.post("/api/conversation")
    def converse(payload: ConversationRequest) -> dict[str, str]:
        try:
            return chat.reply(payload.message.strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=redact_exception(exc)) from exc

    @app.post("/api/central/start")
    def start_central() -> dict[str, Any]:
        return active.start_central()

    @app.post("/api/central/stop")
    def stop_central() -> dict[str, Any]:
        return active.stop_central()

    @app.post("/api/robot/start")
    def start_robot() -> dict[str, Any]:
        return active.start_robot()

    @app.post("/api/robot/stop")
    def stop_robot() -> dict[str, Any]:
        return active.stop_robot()

    @app.post("/api/robot/restart")
    def restart_robot() -> dict[str, Any]:
        return active.restart_robot()

    @app.post("/api/desktop")
    def set_desktop(payload: DesktopToggle) -> dict[str, Any]:
        try:
            return active.set_desktop_enabled(payload.enabled)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/emergency/trigger")
    def emergency_trigger() -> dict[str, Any]:
        return active.trigger_emergency()

    @app.post("/api/emergency/clear")
    def emergency_clear() -> dict[str, Any]:
        return active.clear_emergency()

    @app.post("/api/tasks")
    def submit_task(payload: TaskRequest) -> dict[str, Any]:
        try:
            return active.submit_task(payload.command.strip())
        except (RuntimeError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/guided/explain")
    def explain(payload: GuidedRequest) -> dict[str, Any]:
        return active.explain_guided_command(payload.command)

    return app


def main() -> None:
    cfg = DashboardSettings()
    write_runtime_log(
        "panel",
        f"Painel iniciando em http://{cfg.dashboard_host}:{cfg.dashboard_port}",
        log_dir=cfg.log_dir,
    )
    try:
        uvicorn.run(create_app(), host=cfg.dashboard_host, port=cfg.dashboard_port)
    finally:
        write_runtime_log("panel", "Painel encerrado", log_dir=cfg.log_dir)


if __name__ == "__main__":
    main()
