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
            "robot": {"online": self._robot_online()},
            "desktop": {"enabled": desktop.desktop_enabled},
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
<html lang="pt-BR" data-theme="ultra-dark">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel do Robô</title>
<style>
:root{
  color-scheme:dark;
  --bg:#02050a;--bg2:#040912;--side:#03070d;--card:#07101a;--card2:#091522;--input:#030912;
  --line:#142436;--line2:#1d3550;--ink:#eef5ff;--muted:#9aacc1;--faint:#6f8298;
  --blue:#54a3ff;--blue2:#1677ff;--cyan:#22d3ee;--green:#43e07b;--red:#ff6969;--amber:#eab85e;
  --shadow:rgba(0,0,0,.48)
}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--bg);color:var(--ink)}
body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:15px;line-height:1.52;background:
radial-gradient(circle at 78% -12%,rgba(22,119,255,.10),transparent 31rem),
radial-gradient(circle at 20% 105%,rgba(34,211,238,.035),transparent 28rem),var(--bg)}
button,input,textarea{font:inherit}button:focus-visible,input:focus-visible,textarea:focus-visible,.switch:focus-visible{outline:2px solid var(--cyan);outline-offset:2px}
.shell{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh}
.side{background:rgba(3,7,13,.96);border-right:1px solid var(--line);padding:24px 14px 18px;position:sticky;top:0;height:100vh;display:flex;flex-direction:column}
.brand{display:flex;gap:10px;align-items:center;font-size:19px;font-weight:850;color:#f7fbff;margin-bottom:28px}.brand-icon{font-size:26px}.brand small{display:block;color:var(--muted);font-size:11px;font-weight:550;margin-top:1px}
.nav{display:grid;gap:6px}.nav button{width:100%;border:1px solid transparent;background:transparent;text-align:left;padding:11px 12px;border-radius:10px;font-weight:690;color:#aebed0;cursor:pointer;transition:.16s ease}
.nav button:hover{background:#07111c;color:#dbeaff;border-color:#10233a}.nav button.active{background:linear-gradient(90deg,#0b1d35,#071422);border-color:#194c83;color:#9fceff;box-shadow:inset 2px 0 0 var(--blue)}
.side-note{margin-top:auto;padding:13px;border:1px solid var(--line);border-radius:12px;background:#040a11;color:var(--muted);font-size:12px}.side-note-head{display:flex;justify-content:space-between;gap:8px;color:#c5d4e4;margin-bottom:8px}.online{color:var(--green);font-weight:800;font-size:11px}
.side-version{display:flex;justify-content:space-between;gap:10px;border-top:1px solid var(--line);margin-top:12px;padding-top:10px;color:var(--faint);font-size:11px}
.main{padding:25px 26px 66px;max-width:1540px;width:100%}.top{display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:18px}.title-wrap{position:relative;padding-left:14px}.title-wrap:before{content:"";position:absolute;left:0;top:5px;bottom:5px;width:3px;border-radius:3px;background:linear-gradient(var(--cyan),var(--blue2));box-shadow:0 0 14px rgba(34,211,238,.35)}.top h1{margin:0;font-size:29px;letter-spacing:-.02em;color:#f8fbff}.top p{margin:3px 0 0;color:var(--muted);font-size:14px}
.grid{display:grid;gap:12px}.status-grid{grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:12px}
.card{background:linear-gradient(180deg,rgba(10,21,34,.96),rgba(5,12,20,.98));border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 12px 28px var(--shadow);transition:.16s ease}.card:hover{border-color:#25415f}
.status-card{min-height:118px;position:relative;overflow:hidden}.status-card:after{content:"";position:absolute;right:-28px;bottom:-42px;width:110px;height:110px;border-radius:50%;background:radial-gradient(circle,rgba(84,163,255,.07),transparent 66%)}
.status{display:flex;align-items:center;justify-content:space-between;gap:10px}.status-title{display:flex;align-items:center;gap:9px;font-weight:800}.status-icon{width:34px;height:34px;display:grid;place-items:center;border:1px solid #244664;border-radius:50%;background:#06101b;font-size:17px}
.dot{width:8px;height:8px;border-radius:50%;background:#627386;display:inline-block;margin-right:6px}.on .dot{background:var(--green);box-shadow:0 0 10px rgba(67,224,123,.6)}.bad .dot{background:var(--red);box-shadow:0 0 10px rgba(255,105,105,.55)}
.badge{font-size:11px;padding:4px 8px;border:1px solid #263b51;border-radius:999px;background:#07121e;color:#b8c7d7;white-space:nowrap}.on .badge{background:#062016;border-color:#16512f;color:#70ec97}.bad .badge{background:#260d12;border-color:#64202a;color:#ff9c9c}
.muted{color:var(--muted);font-size:13.5px}.status-card .muted{margin:12px 0 0;padding-left:43px}
.ops{grid-template-columns:1.02fr 1fr 1.08fr}.section-title{display:flex;align-items:center;gap:8px;font-size:16px;font-weight:850;color:#f4f9ff;margin-bottom:13px}.section-kicker{color:var(--cyan)}
.buttons{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.btn{border:1px solid var(--line2);background:#08131f;color:#dbe8f6;border-radius:10px;padding:11px 12px;font-weight:760;cursor:pointer;transition:.14s ease}.btn:hover{background:#0b1928;border-color:#2f5a83}.btn:active{transform:translateY(1px)}
.btn.primary{background:linear-gradient(180deg,#1267dd,#0c51b9);border-color:#2783f5;color:white;box-shadow:0 7px 20px rgba(22,119,255,.15)}.btn.primary:hover{background:linear-gradient(180deg,#1875f3,#0f5dce)}
.btn.green{background:#062216;color:#72efa0;border-color:#145a33}.btn.green:hover{background:#082b1c}.btn.red{background:#251014;color:#ff9393;border-color:#64252d}.btn.red:hover{background:#31151a}.btn.emergency{font-weight:900;letter-spacing:.01em}
textarea,input{width:100%;border:1px solid #23405e;background:var(--input);color:var(--ink);border-radius:10px;padding:12px 13px;caret-color:var(--cyan)}textarea::placeholder,input::placeholder{color:#647b93}textarea{min-height:130px;resize:vertical}.row{display:flex;gap:8px;margin-top:9px}.row .btn{flex:1}
.command-note{display:flex;gap:8px;margin-top:12px;color:#7f94aa;font-size:12px}
.tasks{display:flex;flex-direction:column;gap:7px;max-height:355px;overflow:auto;padding-right:2px}.task{position:relative;border:1px solid #152a3e;background:#050d16;border-radius:9px;padding:9px 9px 9px 31px}.task:before{content:"✓";position:absolute;left:10px;top:10px;width:14px;height:14px;border-radius:50%;display:grid;place-items:center;font-size:9px;color:#66f194;border:1px solid #1d8747;background:#062316}.task b{display:block;font-size:13px;color:#e9f2fc}.task small{color:#8398ae}.task-status{float:right;font-size:10px;padding:3px 7px;background:#071b35;border:1px solid #143c6a;border-radius:9px;color:#78b7ff}
.lower{grid-template-columns:1.1fr 1fr;margin-top:12px}.console{background:#010408;color:#aabed3;border:1px solid #14283c;border-radius:10px;padding:12px;font:12px ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;min-height:180px;max-height:300px;overflow:auto}
.process-list{display:grid;gap:10px}.process-step{display:grid;grid-template-columns:28px 1fr;gap:10px;align-items:start;padding:8px 0;border-bottom:1px solid #102132}.process-step:last-child{border:0}.step-num{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:#071b31;border:1px solid #174a78;color:#7fc0ff;font-size:11px;font-weight:850}
.config-grid{grid-template-columns:1.04fr .96fr}.config-card{min-height:260px}.switchline{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:13px 0 16px;border-bottom:1px solid #13263a}.switch{width:50px;height:27px;background:#202d3c;border:1px solid #3b5067;border-radius:30px;padding:2px;cursor:pointer;flex:0 0 auto}.switch span{display:block;width:21px;height:21px;background:#dce8f5;border-radius:50%;transition:.15s}.switch.on{background:#0f62ce;border-color:#328bf1}.switch.on span{transform:translateX(23px);background:white}
.safety-actions{display:grid;gap:10px;margin-top:14px}.safety-actions .btn{display:flex;justify-content:space-between;align-items:center;text-align:left;padding:14px}.safety-actions .btn span{display:block;font-size:12px;font-weight:550;opacity:.76;margin-top:2px}
.diag-card{margin-top:12px}.diag-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.diag{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}.diag div{padding:10px;border:1px solid #142a40;border-radius:9px;background:#050d16}
.learn{grid-template-columns:1.02fr .98fr}.lab-input{height:64px;font-size:15px}.tips{margin-top:14px;padding:14px;border:1px solid #142a40;border-radius:10px;background:#050d16}.tips ul{margin:8px 0 0;padding-left:18px;color:var(--muted)}.tips li{margin:6px 0}
.flow{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}.flow-node{text-align:center;padding:13px 6px;border:1px solid #142a40;border-radius:10px;background:#050d16}.flow-node strong{display:block;font-size:13px;margin-top:4px}.flow-node span{font-size:11px;color:var(--muted)}.flow-icon{font-size:22px}
.explain{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-top:12px}.explain div{padding:12px;border-radius:9px;background:#050d16;border:1px solid #142a40}.explain b{display:block;margin-bottom:5px;color:#f0f6fd}
.footerbar{position:fixed;left:220px;right:0;bottom:0;height:42px;background:rgba(2,5,10,.94);backdrop-filter:blur(10px);border-top:1px solid #122439;display:flex;align-items:center;justify-content:space-between;padding:0 25px;color:#8296ab;font-size:11px;z-index:9}.footerbar strong{color:#63e68d}.footer-items{display:flex;gap:20px;align-items:center}
.hidden{display:none!important}.message{position:fixed;right:22px;bottom:54px;background:#091827;color:#f0f7ff;border:1px solid #284766;box-shadow:0 12px 34px rgba(0,0,0,.5);padding:12px 15px;border-radius:10px;display:none;max-width:430px;z-index:20}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-track{background:#02050a}::-webkit-scrollbar-thumb{background:#172b40;border:3px solid #02050a;border-radius:20px}
@media(max-width:1120px){.shell{grid-template-columns:1fr}.side{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}.side-note{margin-top:18px}.nav{grid-template-columns:repeat(4,auto);justify-content:start}.nav button{width:auto}.status-grid,.ops,.lower,.config-grid,.learn{grid-template-columns:1fr 1fr}.main{padding:18px 18px 66px}.footerbar{left:0}}
@media(max-width:760px){.status-grid,.ops,.lower,.config-grid,.learn{grid-template-columns:1fr}.nav{grid-template-columns:1fr 1fr}.main{padding:14px 14px 66px}.top{align-items:flex-start}.top h1{font-size:24px}.footer-items{gap:8px}.footer-items span:nth-child(n+3){display:none}.flow{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<div class="shell">
<aside class="side">
  <div class="brand"><div class="brand-icon">🤖</div><div>Painel do Robô<small>Operação + aprendizado</small></div></div>
  <div class="nav">
    <button class="active" data-tab="overview">⌂ &nbsp; Visão geral</button>
    <button data-tab="config">⚙ &nbsp; Configurações</button>
    <button data-tab="learning">⚗ &nbsp; Laboratório</button>
    <button id="refreshBtn">↻ &nbsp; Atualizar</button>
  </div>
  <div class="side-note">
    <div class="side-note-head"><span>Painel local</span><span class="online">ONLINE ●</span></div>
    O Painel continua disponível mesmo quando Central ou Robô são reiniciados.
    <div class="side-version"><span>MVP 0.3</span><span>localhost</span></div>
  </div>
</aside>

<main class="main">
<div class="top">
  <div class="title-wrap"><h1 id="pageTitle">Painel de Operação e Controle</h1><p id="pageSubtitle">Ligue, desligue, monitore e aprenda o Robô passo a passo.</p></div>
  <button class="btn" id="diagBtn">⌁ Diagnóstico</button>
</div>

<section id="overview">
  <div class="grid status-grid">
    <div class="card status-card" id="centralCard"><div class="status"><div class="status-title"><span class="status-icon">▣</span>Central</div><span class="badge"><span class="dot"></span><span class="label">...</span></span></div><p class="muted">Recebe, organiza e distribui as tarefas.</p></div>
    <div class="card status-card" id="robotCard"><div class="status"><div class="status-title"><span class="status-icon">🤖</span>Robô local</div><span class="badge"><span class="dot"></span><span class="label">...</span></span></div><p class="muted">Executa ações permitidas neste computador.</p></div>
    <div class="card status-card" id="desktopCard"><div class="status"><div class="status-title"><span class="status-icon">▤</span>Desktop</div><span class="badge"><span class="dot"></span><span class="label">...</span></span></div><p class="muted">Mouse, teclado, aplicativos e percepção física.</p></div>
    <div class="card status-card" id="emergencyCard"><div class="status"><div class="status-title"><span class="status-icon">🚨</span>Emergência</div><span class="badge"><span class="dot"></span><span class="label">...</span></span></div><p class="muted">Bloqueio persistente e independente do Robô.</p></div>
  </div>

  <div class="grid ops">
    <div class="card">
      <div class="section-title"><span class="section-kicker">ϟ</span>Controles rápidos</div>
      <div class="buttons">
        <button class="btn green" data-action="central/start">▶ Ligar Central</button>
        <button class="btn red" data-action="central/stop">■ Parar Central</button>
        <button class="btn green" data-action="robot/start">▶ Ligar Robô</button>
        <button class="btn red" data-action="robot/stop">■ Parar Robô</button>
        <button class="btn primary" data-action="robot/restart">↻ Reiniciar Robô</button>
        <button class="btn red emergency" data-action="emergency/trigger">🚨 PARADA DE EMERGÊNCIA</button>
      </div>
      <div class="command-note">ⓘ Use a parada de emergência apenas quando precisar interromper o Robô imediatamente.</div>
    </div>

    <div class="card">
      <div class="section-title"><span class="section-kicker">&gt;_</span>Comando para o Robô</div>
      <textarea id="taskCommand" placeholder="Ex.: capturar tela&#10;Ex.: pesquisar inteligência artificial"></textarea>
      <div class="row"><button class="btn primary" id="sendTask">Enviar para o Robô</button><button class="btn" id="clearTask">Limpar</button></div>
      <div class="command-note">♢ Este campo envia tarefas para o planner; não é um terminal de shell.</div>
    </div>

    <div class="card">
      <div class="section-title"><span class="section-kicker">◴</span>Fila e tarefas recentes</div>
      <div id="tasks" class="tasks"><span class="muted">Carregando...</span></div>
    </div>
  </div>

  <div class="grid lower">
    <div class="card"><div class="section-title"><span class="section-kicker">≋</span>Logs ao vivo</div><div class="console" id="logs">Aguardando logs...</div></div>
    <div class="card">
      <div class="section-title"><span class="section-kicker">◇</span>Fluxo atual</div>
      <div class="process-list">
        <div class="process-step"><span class="step-num">1</span><div><b>Você envia um pedido.</b><div class="muted">O Painel entrega a tarefa para a Central.</div></div></div>
        <div class="process-step"><span class="step-num">2</span><div><b>A Central coloca na fila.</b><div class="muted">Ela organiza e guarda o estado.</div></div></div>
        <div class="process-step"><span class="step-num">3</span><div><b>O Robô busca e executa.</b><div class="muted">A política valida a ação antes da execução.</div></div></div>
        <div class="process-step"><span class="step-num">4</span><div><b>O resultado volta.</b><div class="muted">Sucesso, falha e detalhes ficam visíveis.</div></div></div>
      </div>
    </div>
  </div>
</section>

<section id="config" class="hidden">
  <div class="grid config-grid">
    <div class="card config-card">
      <div class="section-title"><span class="section-kicker">♢</span>Permissões e capacidades</div>
      <div class="switchline"><div><b>Controle do Desktop</b><div class="muted">Captura de tela, mouse, teclado e aplicativos tipados.</div></div><div id="desktopSwitch" class="switch" role="switch" tabindex="0"><span></span></div></div>
      <p class="muted">Ao alterar esta opção, reinicie o Robô para ele reler a configuração.</p>
      <div class="row"><button class="btn primary" data-action="robot/restart">↻ Reiniciar Robô</button></div>
    </div>
    <div class="card config-card">
      <div class="section-title"><span style="color:var(--red)">♢</span>Segurança e emergência</div>
      <p class="muted">A parada de emergência cria um bloqueio persistente e tenta encerrar o Robô imediatamente.</p>
      <div class="safety-actions">
        <button class="btn red" data-action="emergency/trigger"><div>🚨 Ativar emergência<span>Bloqueia o Robô imediatamente.</span></div><b>›</b></button>
        <button class="btn green" data-action="emergency/clear"><div>▣ Liberar emergência<span>Remove o bloqueio persistente.</span></div><b>›</b></button>
      </div>
    </div>
  </div>
  <div class="card diag-card">
    <div class="diag-head"><div><div class="section-title"><span class="section-kicker">⌁</span>Diagnóstico rápido</div><div class="muted">Verifique a saúde dos componentes necessários para o controle local.</div></div><button class="btn" id="diagBtnSecondary">Abrir diagnóstico</button></div>
    <div id="diagnostics" class="diag"><span class="muted">Clique em Diagnóstico.</span></div>
  </div>
</section>

<section id="learning" class="hidden">
  <div class="grid learn">
    <div class="card">
      <div class="section-title"><span class="section-kicker">⚗</span>Laboratório de comandos guiados</div>
      <p class="muted">Cole uma linha de manutenção e veja o que ela faz antes de qualquer execução.</p>
      <input class="lab-input" id="guidedCommand" placeholder="Ex.: git pull">
      <div class="row"><button class="btn primary" id="explainBtn">✦ Explicar comando</button><button class="btn" id="copyGuided">▣ Copiar</button></div>
      <div class="tips"><b>ⓘ Dicas rápidas</b><ul><li>O comando não será executado automaticamente.</li><li>Use esta área para entender e validar ações.</li><li>Comandos úteis podem entrar no catálogo guiado.</li></ul></div>
      <div id="explanation" class="explain"></div>
    </div>
    <div class="card">
      <div class="section-title"><span class="section-kicker">▤</span>Princípio didático</div>
      <p><b>Primeiro entender → depois executar.</b></p>
      <p class="muted">O Laboratório explica comandos conhecidos e mantém comandos desconhecidos fora da execução automática.</p>
      <div class="flow">
        <div class="flow-node"><div class="flow-icon">▤</div><strong>Painel</strong><span>Início</span></div>
        <div class="flow-node"><div class="flow-icon">◇</div><strong>Central</strong><span>Organização</span></div>
        <div class="flow-node"><div class="flow-icon">🤖</div><strong>Robô</strong><span>Execução</span></div>
        <div class="flow-node"><div class="flow-icon" style="color:var(--green)">✓</div><strong>Resultado</strong><span>Verificação</span></div>
      </div>
      <div class="command-note">☆ Entender o comando é o primeiro passo para operar o sistema com segurança.</div>
    </div>
  </div>
</section>
</main>
</div>

<div class="footerbar"><div class="footer-items"><span><strong>● Conectado</strong></span><span>Painel local</span><span>Ambiente: Desktop Linux</span><span>Atualização automática de status</span></div><span>127.0.0.1:8765</span></div>
<div id="message" class="message"></div>

<script>
const $=s=>document.querySelector(s); const $$=s=>document.querySelectorAll(s);
const pageCopy={
  overview:['Painel de Operação e Controle','Ligue, desligue, monitore e aprenda o Robô passo a passo.'],
  config:['Configurações','Gerencie permissões, segurança e diagnóstico do Robô.'],
  learning:['Laboratório de comandos guiados','Entenda comandos de manutenção antes de qualquer execução.']
};
function toast(t){const e=$('#message');e.textContent=t;e.style.display='block';setTimeout(()=>e.style.display='none',4200)}
async function api(path,opts={}){const r=await fetch(path,opts);const data=await r.json().catch(()=>({}));if(!r.ok)throw new Error(data.detail||data.message||r.statusText);return data}
function setCard(id,on,label,bad=false){const c=$(id);c.classList.toggle('on',on&&!bad);c.classList.toggle('bad',bad);c.querySelector('.label').textContent=label}
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
async function refresh(){try{const s=await api('/api/status');setCard('#centralCard',s.central.online,s.central.online?'Ligada':'Desligada');setCard('#robotCard',s.robot.online,s.robot.online?'Ligado':'Desligado');setCard('#desktopCard',s.desktop.enabled,s.desktop.enabled?'Habilitado':'Desabilitado');setCard('#emergencyCard',!s.emergency.active,s.emergency.active?'ATIVA':'Normal',s.emergency.active);$('#desktopSwitch').classList.toggle('on',s.desktop.enabled);$('#tasks').innerHTML=s.tasks.length?s.tasks.map(t=>`<div class="task"><span class="task-status">${esc(t.status)}</span><b>${esc(t.command)}</b><small>${esc(t.agent_id||'aguardando Robô')} · tentativa ${esc(t.attempts)}</small></div>`).join(''):'<span class="muted">Nenhuma tarefa ainda.</span>';const logs=[...(s.logs.central||[]).map(x=>'[CENTRAL] '+x),...(s.logs.robot||[]).map(x=>'[ROBÔ] '+x)];$('#logs').textContent=logs.length?logs.join('\n'):'Os processos atuais foram iniciados fora do Painel ou ainda não produziram logs aqui.'}catch(e){toast('Falha ao atualizar: '+e.message)}}
async function action(name){try{const r=await api('/api/'+name,{method:'POST'});toast(r.message||'Ação concluída.');await refresh()}catch(e){toast('Erro: '+e.message)}}
$$('[data-action]').forEach(b=>b.onclick=()=>action(b.dataset.action));$('#refreshBtn').onclick=refresh;
$('#sendTask').onclick=async()=>{const command=$('#taskCommand').value.trim();if(!command)return toast('Digite uma tarefa.');try{const r=await api('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command})});toast('Tarefa criada: '+r.status);await refresh()}catch(e){toast('Erro: '+e.message)}};$('#clearTask').onclick=()=>$('#taskCommand').value='';
$('#desktopSwitch').onclick=async()=>{const enabled=!$('#desktopSwitch').classList.contains('on');try{const r=await api('/api/desktop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled})});toast(r.message+(r.restart_required?' Reinicie o Robô.':''));await refresh()}catch(e){toast('Erro: '+e.message)}};
async function diagnostics(){try{const d=await api('/api/diagnostics');const x=d.desktop;$('#diagnostics').innerHTML=[['Python',d.python.supported],['X11',x.x11_detected],['PyAutoGUI',x.pyautogui_installed],['xdotool',!!x.xdotool],['scrot',!!x.scrot],['Desktop',x.enabled]].map(([n,ok])=>`<div><b>${n}</b><br><span style="color:${ok?'#70ec97':'#eab85e'}">${ok?'✓ OK':'○ verificar'}</span></div>`).join('');$$('[data-tab]').forEach(x=>x.classList.remove('active'));document.querySelector('[data-tab="config"]').classList.add('active');showTab('config')}catch(e){toast('Erro: '+e.message)}}
$('#diagBtn').onclick=diagnostics;$('#diagBtnSecondary').onclick=diagnostics;
function showTab(id){['overview','config','learning'].forEach(x=>$('#'+x).classList.toggle('hidden',x!==id));const copy=pageCopy[id];$('#pageTitle').textContent=copy[0];$('#pageSubtitle').textContent=copy[1]}
$$('[data-tab]').forEach(b=>b.onclick=()=>{$$('[data-tab]').forEach(x=>x.classList.remove('active'));b.classList.add('active');showTab(b.dataset.tab)});
$('#explainBtn').onclick=async()=>{const command=$('#guidedCommand').value.trim();if(!command)return toast('Cole um comando.');try{const r=await api('/api/guided/explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command})});$('#explanation').innerHTML=`<div><b>O que faz</b>${esc(r.what)}</div><div><b>Por que usamos</b>${esc(r.why)}</div><div><b>Resultado esperado</b>${esc(r.expected)}</div><div><b>Onde executar</b>${esc(r.where)}</div>`;if(!r.known)toast('Comando ainda não catalogado: ele não será executado automaticamente.')}catch(e){toast('Erro: '+e.message)}};
$('#copyGuided').onclick=async()=>{const t=$('#guidedCommand').value;await navigator.clipboard.writeText(t);toast('Comando copiado.')};
refresh();setInterval(refresh,2500);
</script>
</body></html>"""


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
