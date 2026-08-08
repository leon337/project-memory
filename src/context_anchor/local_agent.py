from __future__ import annotations

import time
from typing import Any

import httpx

from .actions import ActionExecutor
from .config import LocalAgentSettings
from .emergency_stop import EmergencyStop, EmergencyStopTriggered
from .planner import DeterministicPlanner, Planner
from .policy import evaluate_plan
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
    headers = {"Authorization": f"Bearer {cfg.agent_token}"}
    stop = EmergencyStop(cfg.emergency_stop_path, cfg.agent_pid_path)

    if stop.is_triggered():
        print(
            f"Emergency stop está ativo em {cfg.emergency_stop_path}. "
            "Execute 'context-anchor-stop clear' localmente antes de iniciar o agente."
        )
        return

    executor = ActionExecutor(
        headless=cfg.browser_headless,
        desktop_enabled=cfg.desktop_enabled,
        screenshot_dir=cfg.screenshot_dir,
        emergency_stop=stop,
    )
    planner = DeterministicPlanner()

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

                        try:
                            result = execute_command(executor, task.command, planner=planner)
                            payload = {
                                "lease_token": task.lease_token,
                                "ok": True,
                                "result": result,
                            }
                        except EmergencyStopTriggered as exc:
                            payload = {
                                "lease_token": task.lease_token,
                                "ok": False,
                                "error": f"EmergencyStopTriggered: {exc}",
                            }
                            finish = client.post(f"/api/agent/tasks/{task.id}/result", json=payload)
                            finish.raise_for_status()
                            raise
                        except Exception as exc:
                            payload = {
                                "lease_token": task.lease_token,
                                "ok": False,
                                "error": f"{type(exc).__name__}: {exc}",
                            }

                        finish = client.post(f"/api/agent/tasks/{task.id}/result", json=payload)
                        finish.raise_for_status()
                    except httpx.HTTPError as exc:
                        print(f"Falha de comunicação com o Control Plane: {exc}")
                        time.sleep(max(cfg.poll_interval_seconds, 3))
            except (KeyboardInterrupt, EmergencyStopTriggered):
                pass
            finally:
                executor.close()


if __name__ == "__main__":
    run()
