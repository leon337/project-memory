from __future__ import annotations

import time
from typing import Any

import httpx

from .actions import ActionExecutor
from .config import DashboardSettings, LocalAgentSettings
from .emergency_stop import EmergencyStop, EmergencyStopTriggered
from .planner import DeterministicPlanner, Planner
from .policy import evaluate_plan
from .runtime_log import write_runtime_log
from .schemas import AgentTask


def execute_command(
    executor: ActionExecutor,
    command: str,
    *,
    planner: Planner | None = None,
) -> dict[str, Any]:
    active_planner = planner or DeterministicPlanner()
    plan = active_planner.plan(command)
    decision = evaluate_plan(plan, desktop_enabled=executor.desktop_enabled)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    result = executor.execute(plan)
    result["policy_reason"] = decision.reason
    return result


def run() -> None:
    cfg = LocalAgentSettings()
    dashboard_cfg = DashboardSettings()
    headers = {"Authorization": f"Bearer {cfg.agent_token}"}
    stop = EmergencyStop(cfg.emergency_stop_path, cfg.agent_pid_path)

    def log(message: str, *, level: str = "INFO") -> None:
        write_runtime_log("robot", message, level=level, log_dir=dashboard_cfg.log_dir)

    if stop.is_triggered():
        message = (
            f"Parada de emergência ativa em {cfg.emergency_stop_path}. "
            "Execute 'parar-robo clear' localmente antes de iniciar o Robô."
        )
        log("Inicialização recusada: parada de emergência ativa", level="WARN")
        print(message)
        return

    executor = ActionExecutor(
        headless=cfg.browser_headless,
        desktop_enabled=cfg.desktop_enabled,
        screenshot_dir=cfg.screenshot_dir,
        emergency_stop=stop,
    )
    planner = DeterministicPlanner()

    log(
        f"Robô iniciando agente={cfg.agent_id} desktop={'habilitado' if cfg.desktop_enabled else 'desabilitado'}"
    )
    try:
        with stop.register_agent_process():
            with httpx.Client(base_url=cfg.control_plane_url, headers=headers, timeout=35) as client:
                try:
                    while True:
                        stop.assert_not_triggered()
                        try:
                            response = client.get("/api/agent/next", params={"agent_id": cfg.agent_id})
                            if response.status_code == 204:
                                time.sleep(cfg.poll_interval_seconds)
                                continue
                            response.raise_for_status()
                            task = AgentTask.model_validate(response.json())
                            log(f"Tarefa recebida id={task.id}")

                            try:
                                result = execute_command(executor, task.command, planner=planner)
                                payload = {
                                    "lease_token": task.lease_token,
                                    "ok": True,
                                    "result": result,
                                }
                                log(f"Tarefa executada id={task.id} resultado=sucesso")
                            except EmergencyStopTriggered as exc:
                                payload = {
                                    "lease_token": task.lease_token,
                                    "ok": False,
                                    "error": f"EmergencyStopTriggered: {exc}",
                                }
                                log(f"Tarefa interrompida id={task.id} por parada de emergência", level="WARN")
                                finish = client.post(f"/api/agent/tasks/{task.id}/result", json=payload)
                                finish.raise_for_status()
                                raise
                            except Exception as exc:
                                payload = {
                                    "lease_token": task.lease_token,
                                    "ok": False,
                                    "error": f"{type(exc).__name__}: {exc}",
                                }
                                log(
                                    f"Tarefa falhou id={task.id} erro={type(exc).__name__}: {exc}",
                                    level="ERROR",
                                )

                            finish = client.post(f"/api/agent/tasks/{task.id}/result", json=payload)
                            finish.raise_for_status()
                            log(f"Resultado enviado id={task.id} status={finish.json().get('status', 'desconhecido')}")
                        except httpx.HTTPError as exc:
                            log(f"Falha de comunicação com a Central: {exc}", level="WARN")
                            print(f"Falha de comunicação com a Central: {exc}")
                            time.sleep(max(cfg.poll_interval_seconds, 3))
                except (KeyboardInterrupt, EmergencyStopTriggered):
                    pass
    finally:
        executor.close()
        log("Robô encerrado")


if __name__ == "__main__":
    run()
