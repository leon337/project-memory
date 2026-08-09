from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Protocol

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .config import ControlPlaneSettings, DashboardSettings, DesktopSettings, EmergencyStopSettings
from .doctor import collect_diagnostics
from .emergency_stop import EmergencyStop
from .process_registry import record_is_alive, terminate_registered_process
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
        "where": "Pode ser feito pelo terminal ou pelo botão Ligar Central deste Painel.",
    },
    "robo": {
        "what": "Liga o Robô local, que busca tarefas na Central e executa ações permitidas.",
        "why": "A Central organiza; o Robô é quem realmente executa navegador e desktop.",
        "expected": "O estado do Robô muda para Online e ele começa a consultar a fila.",
        "where": "Pode ser feito pelo terminal ou pelo botão Ligar Robô deste Painel.",
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
        "where": "Terminal ou cartão Emergência deste Painel.",
    },
}


class DesktopToggle(BaseModel):
    enabled: bool


class TaskRequest(BaseModel):
    command: str = Field(min_length=1, max_length=500)


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

    def _tail(self, name: str, lines: int = 40) -> list[str]:
        path = self.project_root / self.dashboard.log_dir / f"{name}.log"
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except FileNotFoundError:
            return []
        return content[-lines:]

    def status(self) -> dict[str, Any]:
        desktop = DesktopSettings()
        emergency = self.stop.status()
        return {
            "central": {
                "online": self._central_online(),
                "managed": record_is_alive(self.dashboard.central_pid_path),
            },
            "robot": {
                "online": self._robot_online(),
            },
            "desktop": {
                "enabled": desktop.desktop_enabled,
            },
            "emergency": emergency,
            "tasks": self.store.list_recent(limit=8),
            "logs": {
                "central": self._tail("central"),
                "robot": self._tail("robot"),
            },
        }

    def diagnostics(self) -> dict[str, Any]:
        return collect_diagnostics()

    def _spawn(self, module: str, log_name: str) -> subprocess.Popen[bytes]:
        log_dir = self.project_root / self.dashboard.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = (log_dir / f"{log_name}.log").open("ab", buffering=0)
        return subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=self.project_root,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            shell=False,
        )

    def start_central(self) -> dict[str, Any]:
        if self._central_online():
            return {"ok": True, "message": "A Central já está online."}
        process = self._spawn("context_anchor.control_plane", "central")
        for _ in range(25):
            if self._central_online():
                return {"ok": True, "message": "Central ligada.", "pid": process.pid}
            if process.poll() is not None:
                break
            time.sleep(0.12)
        return {"ok": False, "message": "A Central não respondeu após a tentativa de início."}

    def stop_central(self) -> dict[str, Any]:
        result = terminate_registered_process(self.dashboard.central_pid_path)
        if result["stopped"]:
            return {"ok": True, "message": "Sinal de parada enviado para a Central.", **result}
        if self._central_online():
            return {
                "ok": False,
                "message": "A Central está online, mas foi iniciada fora do Painel. Pare-a no terminal uma vez e depois ligue-a pelo Painel.",
                **result,
            }
        return {"ok": True, "message": "A Central já está desligada.", **result}

    def start_robot(self) -> dict[str, Any]:
        if self.stop.is_triggered():
            return {"ok": False, "message": "A parada de emergência está ativa. Limpe-a antes de ligar o Robô."}
        if self._robot_online():
            return {"ok": True, "message": "O Robô já está online."}
        if not self._central_online():
            return {"ok": False, "message": "Ligue a Central antes de ligar o Robô."}
        process = self._spawn("context_anchor.local_agent", "robot")
        for _ in range(25):
            if self._robot_online():
                return {"ok": True, "message": "Robô ligado.", "pid": process.pid}
            if process.poll() is not None:
                break
            time.sleep(0.12)
        return {"ok": False, "message": "O Robô não registrou seu processo após a tentativa de início."}

    def stop_robot(self) -> dict[str, Any]:
        result = terminate_registered_process(self.emergency_cfg.agent_pid_path)
        if result["stopped"]:
            return {"ok": True, "message": "Sinal de parada enviado para o Robô.", **result}
        return {"ok": True, "message": "O Robô já estava desligado ou o registro era antigo.", **result}

    def restart_robot(self) -> dict[str, Any]:
        self.stop_robot()
        for _ in range(20):
            if not self._robot_online():
                break
            time.sleep(0.1)
        return self.start_robot()

    def set_desktop_enabled(self, enabled: bool) -> dict[str, Any]:
        env_path = self.project_root / self.dashboard.env_path
        if not env_path.exists():
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
        return {
            "ok": True,
            "enabled": enabled,
            "restart_required": self._robot_online(),
            "message": "Desktop habilitado." if enabled else "Desktop desabilitado.",
        }

    def trigger_emergency(self) -> dict[str, Any]:
        result = self.stop.trigger(reason="Painel do Robô", terminate_process=True)
        return {"ok": True, "message": "Parada de emergência ativada.", **result}

    def clear_emergency(self) -> dict[str, Any]:
        result = self.stop.clear()
        return {"ok": True, "message": "Parada de emergência liberada.", **result}

    def submit_task(self, command: str) -> dict[str, Any]:
        if not self._central_online():
            raise RuntimeError("A Central está desligada.")
        response = httpx.post(
            f"{self._central_url()}/api/tasks",
            headers={"Authorization": f"Bearer {self.control.user_token}"},
            json={"command": command},
            timeout=4,
        )
        response.raise_for_status()
        return response.json()

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
            "expected": "Você pode copiar o comando e me mostrar; então documentamos o que ele faz e, se fizer sentido, adicionamos ao catálogo.",
            "where": "Não será executado automaticamente nesta versão.",
        }


INDEX_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel do Robô</title>
<style>
:root{color-scheme:dark;--blue:#6ea8fe;--blue-strong:#3b82f6;--green:#56d364;--red:#ff6b6b;--amber:#e3b341;--ink:#e6edf3;--muted:#93a4b8;--line:#273446;--line-strong:#36465d;--bg:#0a0f16;--side:#0d141d;--card:#111a25;--card-hover:#152131;--input:#0c131c;--soft:#172231;--shadow:rgba(0,0,0,.28)}
*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);line-height:1.45}
button,input,textarea{font:inherit}button:focus-visible,input:focus-visible,textarea:focus-visible,.switch:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}.side{background:var(--side);border-right:1px solid var(--line);padding:24px 16px;position:sticky;top:0;height:100vh;box-shadow:8px 0 30px rgba(0,0,0,.12)}
.brand{font-size:20px;font-weight:800;margin-bottom:28px;color:#f0f6fc}.brand small{display:block;font-size:12px;color:var(--muted);font-weight:500;margin-top:4px}
.nav button{width:100%;border:1px solid transparent;background:transparent;text-align:left;padding:12px;border-radius:10px;margin:3px 0;font-weight:650;color:#b8c6d8;cursor:pointer;transition:background .15s,border-color .15s,color .15s}.nav button.active,.nav button:hover{background:#16243a;border-color:#233958;color:#8fbcff}
.main{padding:24px 28px 50px;max-width:1500px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.top h1{margin:0;font-size:27px;color:#f0f6fc}.top p{margin:5px 0;color:var(--muted)}
.grid{display:grid;gap:14px}.status-grid{grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:14px}.card{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:17px;box-shadow:0 8px 24px var(--shadow);transition:border-color .15s,background .15s}.card:hover{border-color:var(--line-strong);background:var(--card-hover)}
.status{display:flex;align-items:center;justify-content:space-between;gap:10px}.dot{width:10px;height:10px;border-radius:99px;background:#738196;display:inline-block;margin-right:7px;box-shadow:0 0 0 3px rgba(115,129,150,.08)}.on .dot{background:var(--green);box-shadow:0 0 0 3px rgba(86,211,100,.10)}.bad .dot{background:var(--red);box-shadow:0 0 0 3px rgba(255,107,107,.10)}
.badge{font-size:12px;padding:5px 9px;border:1px solid #334155;border-radius:20px;background:#17202d;color:#b6c2d2;white-space:nowrap}.on .badge{background:#10251a;border-color:#214f31;color:#7ee787}.bad .badge{background:#2b1719;border-color:#5a292e;color:#ff9b9b}
.ops{grid-template-columns:1.05fr 1fr 1.1fr}.section-title{font-size:16px;font-weight:800;margin-bottom:13px;color:#f0f6fc}.buttons{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.btn{border:1px solid var(--line-strong);background:#151e2a;color:#d8e2ef;border-radius:10px;padding:11px 12px;font-weight:750;cursor:pointer;transition:transform .12s,background .15s,border-color .15s}.btn:hover{background:#1a2635;border-color:#49617f}.btn:active{transform:translateY(1px)}.btn.primary{background:#245db5;color:#f8fbff;border-color:#3575d3}.btn.primary:hover{background:#2c6ac8}.btn.green{background:#12301d;color:#7ee787;border-color:#285f38}.btn.green:hover{background:#173b24}.btn.red{background:#32191c;color:#ff9b9b;border-color:#6b3036}.btn.red:hover{background:#402026}.btn.amber{background:#332813;color:#f0cf69;border-color:#66501d}
textarea,input{width:100%;border:1px solid var(--line-strong);background:var(--input);color:var(--ink);border-radius:10px;padding:11px;caret-color:var(--blue)}textarea::placeholder,input::placeholder{color:#708198}textarea{min-height:112px;resize:vertical}.row{display:flex;gap:8px;margin-top:9px}.row .btn{flex:1}
.tasks{display:flex;flex-direction:column;gap:8px}.task{border:1px solid var(--line);background:#0f1722;border-radius:10px;padding:10px}.task b{display:block;font-size:13px;color:#dce6f2}.task small{color:var(--muted)}.task-status{float:right;font-size:11px;padding:3px 7px;background:#1a2940;border:1px solid #2a4163;border-radius:10px;color:#a9c7f5}
.lower{grid-template-columns:1.1fr 1fr;margin-top:14px}.console{background:#070b10;color:#b8c7d9;border:1px solid #222d3a;border-radius:10px;padding:12px;font:12px ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;min-height:190px;max-height:310px;overflow:auto;box-shadow:inset 0 1px 0 rgba(255,255,255,.02)}
.switchline{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line)}.switch{width:48px;height:26px;background:#364152;border:1px solid #4a586d;border-radius:30px;padding:2px;cursor:pointer}.switch span{display:block;width:20px;height:20px;background:#d7e0ea;border-radius:50%;transition:.15s}.switch.on{background:#245db5;border-color:#4b86df}.switch.on span{transform:translateX(22px);background:white}
.learn{grid-template-columns:1.1fr 1fr;margin-top:14px}.explain{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:11px}.explain div{padding:12px;border-radius:10px;background:#0f1722;border:1px solid var(--line)}.explain b{display:block;margin-bottom:5px;color:#edf4fc}.muted{color:var(--muted);font-size:13px}.hidden{display:none!important}.diag{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.diag div{padding:10px;border:1px solid var(--line);border-radius:9px;background:#0f1722}.message{position:fixed;right:25px;bottom:25px;background:#1a2635;color:#f0f6fc;border:1px solid #3a4b63;box-shadow:0 10px 30px rgba(0,0,0,.35);padding:12px 16px;border-radius:10px;display:none;max-width:420px;z-index:20}
::-webkit-scrollbar{width:11px;height:11px}::-webkit-scrollbar-track{background:#0a0f16}::-webkit-scrollbar-thumb{background:#2b394b;border:3px solid #0a0f16;border-radius:20px}::-webkit-scrollbar-thumb:hover{background:#3b4c63}
@media(max-width:1050px){.shell{grid-template-columns:1fr}.side{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line);box-shadow:none}.nav{display:flex;gap:5px;flex-wrap:wrap}.nav button{width:auto}.status-grid,.ops,.lower,.learn{grid-template-columns:1fr 1fr}.main{padding:18px}}@media(max-width:720px){.status-grid,.ops,.lower,.learn{grid-template-columns:1fr}.side{padding:14px}.main{padding:14px}.top{align-items:flex-start;gap:10px}.top h1{font-size:23px}}
</style>
</head>
<body><div class="shell">
<aside class="side"><div class="brand">🤖 Painel do Robô<small>Operação + aprendizado</small></div><div class="nav">
<button class="active" data-tab="overview">🏠 Visão geral</button><button data-tab="config">⚙️ Configurações</button><button data-tab="learning">🧪 Laboratório</button><button id="refreshBtn">↻ Atualizar</button>
</div><div style="margin-top:28px" class="muted">O Painel é independente da Central e do Robô. Ele continua aberto para você diagnosticar e religar os componentes.</div></aside>
<main class="main">
<div class="top"><div><h1>Painel de Operação e Controle</h1><p>Ligue, desligue, monitore e aprenda o Robô passo a passo.</p></div><button class="btn" id="diagBtn">🩺 Diagnóstico</button></div>
<section id="overview">
<div class="grid status-grid">
<div class="card" id="centralCard"><div class="status"><b>🗄️ Central</b><span class="badge"><span class="dot"></span><span class="label">...</span></span></div><p class="muted">Recebe e organiza as tarefas.</p></div>
<div class="card" id="robotCard"><div class="status"><b>🤖 Robô local</b><span class="badge"><span class="dot"></span><span class="label">...</span></span></div><p class="muted">Executa ações neste computador.</p></div>
<div class="card" id="desktopCard"><div class="status"><b>🖥️ Desktop</b><span class="badge"><span class="dot"></span><span class="label">...</span></span></div><p class="muted">Mouse, teclado e percepção física.</p></div>
<div class="card" id="emergencyCard"><div class="status"><b>🚨 Emergência</b><span class="badge"><span class="dot"></span><span class="label">...</span></span></div><p class="muted">Bloqueio independente do Robô.</p></div>
</div>
<div class="grid ops">
<div class="card"><div class="section-title">Controles rápidos</div><div class="buttons">
<button class="btn green" data-action="central/start">▶ Ligar Central</button><button class="btn red" data-action="central/stop">■ Parar Central</button><button class="btn green" data-action="robot/start">▶ Ligar Robô</button><button class="btn red" data-action="robot/stop">■ Parar Robô</button><button class="btn primary" data-action="robot/restart">↻ Reiniciar Robô</button><button class="btn red" data-action="emergency/trigger">🚨 PARADA DE EMERGÊNCIA</button>
</div></div>
<div class="card"><div class="section-title">Comando para o Robô</div><textarea id="taskCommand" placeholder="Ex.: capturar tela&#10;Ex.: pesquisar inteligência artificial"></textarea><div class="row"><button class="btn primary" id="sendTask">Enviar para o Robô</button><button class="btn" id="clearTask">Limpar</button></div><p class="muted">Este campo envia tarefas para o planner do Robô; não é um terminal de shell.</p></div>
<div class="card"><div class="section-title">Fila e tarefas recentes</div><div id="tasks" class="tasks"><span class="muted">Carregando...</span></div></div>
</div>
<div class="grid lower"><div class="card"><div class="section-title">Logs ao vivo</div><div class="console" id="logs">Aguardando logs...</div></div>
<div class="card"><div class="section-title">O que está acontecendo agora</div><p><b>1. Você envia um pedido.</b><br><span class="muted">O Painel entrega a tarefa para a Central.</span></p><p><b>2. A Central coloca na fila.</b><br><span class="muted">Ela organiza e guarda o estado.</span></p><p><b>3. O Robô busca e executa.</b><br><span class="muted">A política valida antes da ação.</span></p><p><b>4. O resultado volta.</b><br><span class="muted">Você vê sucesso, falha e detalhes.</span></p></div></div>
</section>
<section id="config" class="hidden"><div class="grid lower">
<div class="card"><div class="section-title">Permissões e capacidades</div><div class="switchline"><div><b>Controle do Desktop</b><div class="muted">Captura de tela, mouse, teclado e aplicativos tipados.</div></div><div id="desktopSwitch" class="switch"><span></span></div></div><p class="muted">Ao alterar esta opção, reinicie o Robô para ele reler a configuração.</p><div class="row"><button class="btn primary" data-action="robot/restart">Reiniciar Robô</button></div></div>
<div class="card"><div class="section-title">Segurança e emergência</div><p>A parada de emergência cria um bloqueio persistente e tenta encerrar o Robô imediatamente.</p><div class="row"><button class="btn red" data-action="emergency/trigger">Ativar emergência</button><button class="btn green" data-action="emergency/clear">Liberar emergência</button></div></div>
</div><div class="card" style="margin-top:14px"><div class="section-title">Diagnóstico rápido</div><div id="diagnostics" class="diag"><span class="muted">Clique em Diagnóstico.</span></div></div></section>
<section id="learning" class="hidden"><div class="grid learn">
<div class="card"><div class="section-title">Laboratório de comandos guiados</div><p class="muted">Cole aqui uma linha que eu te fornecer. O Painel explica antes de qualquer ação.</p><input id="guidedCommand" placeholder="Ex.: git pull"><div class="row"><button class="btn primary" id="explainBtn">Explicar comando</button><button class="btn" id="copyGuided">Copiar</button></div><div id="explanation" class="explain"></div></div>
<div class="card"><div class="section-title">Princípio didático</div><p><b>Primeiro entender → depois executar.</b></p><p class="muted">O laboratório não executa automaticamente comandos desconhecidos de terminal. Quando um comando for útil e seguro para o fluxo do projeto, ele poderá entrar no catálogo guiado.</p><p><b>Fluxo mental:</b></p><p class="muted">Painel → Central → Robô → ação permitida → resultado.</p></div>
</div></section>
</main></div><div id="message" class="message"></div>
<script>
const $=s=>document.querySelector(s); const $$=s=>document.querySelectorAll(s);
function toast(t){const e=$('#message');e.textContent=t;e.style.display='block';setTimeout(()=>e.style.display='none',4200)}
async function api(path,opts={}){const r=await fetch(path,opts);const data=await r.json().catch(()=>({}));if(!r.ok)throw new Error(data.detail||data.message||r.statusText);return data}
function setCard(id,on,label,bad=false){const c=$(id);c.classList.toggle('on',on&&!bad);c.classList.toggle('bad',bad);c.querySelector('.label').textContent=label}
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
async function refresh(){try{const s=await api('/api/status');setCard('#centralCard',s.central.online,s.central.online?'Ligada':'Desligada');setCard('#robotCard',s.robot.online,s.robot.online?'Ligado':'Desligado');setCard('#desktopCard',s.desktop.enabled,s.desktop.enabled?'Habilitado':'Desabilitado');setCard('#emergencyCard',!s.emergency.active,s.emergency.active?'ATIVA':'Normal',s.emergency.active);$('#desktopSwitch').classList.toggle('on',s.desktop.enabled);$('#tasks').innerHTML=s.tasks.length?s.tasks.map(t=>`<div class="task"><span class="task-status">${esc(t.status)}</span><b>${esc(t.command)}</b><small>${esc(t.agent_id||'aguardando Robô')} · tentativa ${esc(t.attempts)}</small></div>`).join(''):'<span class="muted">Nenhuma tarefa ainda.</span>';const logs=[...(s.logs.central||[]).map(x=>'[CENTRAL] '+x),...(s.logs.robot||[]).map(x=>'[ROBÔ] '+x)];$('#logs').textContent=logs.length?logs.join('\n'):'Os processos atuais foram iniciados fora do Painel ou ainda não produziram logs aqui.'}catch(e){toast('Falha ao atualizar: '+e.message)}}
async function action(name){try{const r=await api('/api/'+name,{method:'POST'});toast(r.message||'Ação concluída.');await refresh()}catch(e){toast('Erro: '+e.message)}}
$$('[data-action]').forEach(b=>b.onclick=()=>action(b.dataset.action));$('#refreshBtn').onclick=refresh;
$('#sendTask').onclick=async()=>{const command=$('#taskCommand').value.trim();if(!command)return toast('Digite uma tarefa.');try{const r=await api('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command})});toast('Tarefa criada: '+r.status);await refresh()}catch(e){toast('Erro: '+e.message)}};$('#clearTask').onclick=()=>$('#taskCommand').value='';
$('#desktopSwitch').onclick=async()=>{const enabled=!$('#desktopSwitch').classList.contains('on');try{const r=await api('/api/desktop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled})});toast(r.message+(r.restart_required?' Reinicie o Robô.':''));await refresh()}catch(e){toast('Erro: '+e.message)}};
$('#diagBtn').onclick=async()=>{try{const d=await api('/api/diagnostics');const x=d.desktop;$('#diagnostics').innerHTML=[['Python',d.python.supported],['X11',x.x11_detected],['PyAutoGUI',x.pyautogui_installed],['xdotool',!!x.xdotool],['scrot',!!x.scrot],['Desktop',x.enabled]].map(([n,ok])=>`<div><b>${n}</b><br><span style="color:${ok?'#7ee787':'#e3b341'}">${ok?'✓ OK':'○ verificar'}</span></div>`).join('');$$('[data-tab]').forEach(x=>x.classList.remove('active'));document.querySelector('[data-tab="config"]').classList.add('active');showTab('config')}catch(e){toast('Erro: '+e.message)}};
function showTab(id){['overview','config','learning'].forEach(x=>$('#'+x).classList.toggle('hidden',x!==id))}$$('[data-tab]').forEach(b=>b.onclick=()=>{$$('[data-tab]').forEach(x=>x.classList.remove('active'));b.classList.add('active');showTab(b.dataset.tab)});
$('#explainBtn').onclick=async()=>{const command=$('#guidedCommand').value.trim();if(!command)return toast('Cole um comando.');try{const r=await api('/api/guided/explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command})});$('#explanation').innerHTML=`<div><b>O que faz</b>${esc(r.what)}</div><div><b>Por que usamos</b>${esc(r.why)}</div><div><b>Resultado esperado</b>${esc(r.expected)}</div><div><b>Onde executar</b>${esc(r.where)}</div>`;if(!r.known)toast('Comando ainda não catalogado: ele não será executado automaticamente.') }catch(e){toast('Erro: '+e.message)}};
$('#copyGuided').onclick=async()=>{const t=$('#guidedCommand').value;await navigator.clipboard.writeText(t);toast('Comando copiado.')};
refresh();setInterval(refresh,2500);
</script></body></html>"""


def create_app(controller: DashboardControl | None = None) -> FastAPI:
    active = controller or DashboardController()
    app = FastAPI(title="Painel do Robô", version="0.3.0")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return active.status()

    @app.get("/api/diagnostics")
    def diagnostics() -> dict[str, Any]:
        return active.diagnostics()

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
    uvicorn.run(create_app(), host=cfg.dashboard_host, port=cfg.dashboard_port)


if __name__ == "__main__":
    main()
