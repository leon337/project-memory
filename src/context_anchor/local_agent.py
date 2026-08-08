from __future__ import annotations

import time
from typing import Any

import httpx

from .actions import ActionExecutor
from .config import LocalAgentSettings
from .policy import evaluate_plan, plan_command
from .schemas import AgentTask


def execute_command(executor: ActionExecutor, command: str) -> dict[str, Any]:
    plan = plan_command(command)
    decision = evaluate_plan(plan)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    result = executor.execute(plan)
    result["policy_reason"] = decision.reason
    return result


def run() -> None:
    cfg = LocalAgentSettings()
    headers = {"Authorization": f"Bearer {cfg.agent_token}"}
    executor = ActionExecutor(headless=cfg.browser_headless)

    with httpx.Client(base_url=cfg.control_plane_url, headers=headers, timeout=35) as client:
        try:
            while True:
                try:
                    response = client.get("/api/agent/next", params={"agent_id": cfg.agent_id})
                    if response.status_code == 204:
                        time.sleep(cfg.poll_interval_seconds)
                        continue
                    response.raise_for_status()
                    task = AgentTask.model_validate(response.json())

                    try:
                        result = execute_command(executor, task.command)
                        payload = {"ok": True, "result": result}
                    except Exception as exc:
                        payload = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

                    finish = client.post(f"/api/agent/tasks/{task.id}/result", json=payload)
                    finish.raise_for_status()
                except httpx.HTTPError as exc:
                    print(f"Falha de comunicação com o Control Plane: {exc}")
                    time.sleep(max(cfg.poll_interval_seconds, 3))
        except KeyboardInterrupt:
            pass
        finally:
            executor.close()


if __name__ == "__main__":
    run()
