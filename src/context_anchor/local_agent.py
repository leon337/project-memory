from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .actions import ActionExecutor
from .config import DashboardSettings, LocalAgentSettings
from .emergency_stop import EmergencyStop, EmergencyStopTriggered
from .planner import (
    DeterministicPlanner,
    MultiProviderPlanner,
    Planner,
    ProviderCandidate,
)
from .policy import Plan, evaluate_plan
from .providers import CloudflareWorkersAIProvider, GeminiProvider, ZAIProvider
from .runtime_log import write_runtime_log
from .schemas import AgentTask


_OBSERVATION_KEYS = (
    "action",
    "app",
    "executable",
    "argv",
    "pid",
    "window_changed",
    "window_id",
    "window_title",
    "verified",
    "characters",
    "key",
    "x",
    "y",
    "requested_url",
    "final_url",
    "title",
    "http_status",
    "width",
    "height",
)


def build_planner(cfg: LocalAgentSettings) -> Planner:
    if cfg.planner_mode == "deterministic":
        return DeterministicPlanner()

    candidates: list[ProviderCandidate] = []

    if cfg.cloudflare_api_token and cfg.cloudflare_account_id:
        candidates.append(
            ProviderCandidate(
                name="cloudflare",
                provider=CloudflareWorkersAIProvider(
                    cfg.cloudflare_api_token,
                    cfg.cloudflare_account_id,
                    model=cfg.cloudflare_model,
                    timeout_seconds=cfg.planner_timeout_seconds,
                ),
                roles=frozenset({"fast", "reasoning"}),
                rpm_limit=cfg.cloudflare_rpm_limit,
            )
        )

    if cfg.zai_api_key:
        candidates.append(
            ProviderCandidate(
                name="zai",
                provider=ZAIProvider(
                    cfg.zai_api_key,
                    model=cfg.zai_model,
                    timeout_seconds=cfg.planner_timeout_seconds,
                ),
                roles=frozenset({"fast", "reasoning"}),
            )
        )

    if cfg.gemini_api_key:
        candidates.append(
            ProviderCandidate(
                name="gemini",
                provider=GeminiProvider(
                    cfg.gemini_api_key,
                    model=cfg.gemini_model,
                    timeout_seconds=cfg.planner_timeout_seconds,
                ),
                roles=frozenset({"fast", "reasoning"}),
                rpm_limit=cfg.gemini_rpm_limit,
            )
        )

    if not candidates:
        raise ValueError(
            "CONTEXT_ANCHOR_PLANNER_MODE=multi exige ao menos um provedor com credencial local configurada."
        )

    return MultiProviderPlanner(
        candidates,
        deterministic=DeterministicPlanner(),
        cooldown_seconds=cfg.planner_cooldown_seconds,
    )


def _planner_snapshot(planner: Planner) -> dict[str, Any]:
    errors = getattr(planner, "last_errors", None) or {}
    return {
        "provider": getattr(planner, "last_provider", None),
        "route": getattr(planner, "last_route", None),
        "fallbacks": sorted(str(name) for name in errors),
    }


def _compact_observation(result: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in _OBSERVATION_KEYS:
        if key not in result:
            continue
        value = result[key]
        if isinstance(value, str):
            compact[key] = value[:240]
        elif isinstance(value, (bool, int, float)) or value is None:
            compact[key] = value
        elif isinstance(value, list):
            compact[key] = [str(item)[:120] for item in value[:12]]
    return compact


def _goal_followup_prompt(objective: str, steps: list[dict[str, Any]]) -> str:
    history = [
        {
            "step": step["step"],
            "action": step["action"],
            "target": step["target"],
            "verified": step["verified"],
            "observation": step["observation"],
        }
        for step in steps
    ]
    return (
        "OBJETIVO ORIGINAL:\n"
        f"{objective}\n\n"
        "HISTÓRICO DE ETAPAS JÁ EXECUTADAS E OBSERVADAS:\n"
        f"{json.dumps(history, ensure_ascii=False)}\n\n"
        "Decida somente a PRÓXIMA ação necessária. "
        "Não repita uma etapa já verificada sem necessidade. "
        "Se ainda faltar qualquer parte do objetivo original, continue executando. "
        "Use action=finish somente quando o objetivo estiver integralmente concluído."
    )


def _execute_one(executor: ActionExecutor, plan: Plan) -> dict[str, Any]:
    decision = evaluate_plan(plan, desktop_enabled=executor.desktop_enabled)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    result = executor.execute(plan)
    result["policy_reason"] = decision.reason
    return result


def _execute_goal_loop(
    executor: ActionExecutor,
    objective: str,
    planner: Planner,
    first_plan: Plan,
    *,
    max_goal_steps: int,
) -> dict[str, Any]:
    plan = first_plan
    steps: list[dict[str, Any]] = []
    planner_trace: list[dict[str, Any]] = []
    all_fallbacks: set[str] = set()

    while True:
        snapshot = _planner_snapshot(planner)
        all_fallbacks.update(snapshot["fallbacks"])
        planner_trace.append(
            {
                "decision": len(planner_trace) + 1,
                "provider": snapshot["provider"],
                "route": snapshot["route"],
                "fallbacks": snapshot["fallbacks"],
                "action": plan.action,
                "target": plan.target,
            }
        )

        if plan.action == "finish":
            if not steps:
                raise RuntimeError("O planner tentou concluir o objetivo sem executar nenhuma etapa verificável.")
            return {
                "action": "goal",
                "goal_completed": True,
                "completion": plan.target,
                "steps": steps,
                "verified": all(step["verified"] is not False for step in steps),
                "planner_provider": snapshot["provider"],
                "planner_route": snapshot["route"],
                "planner_fallbacks": sorted(all_fallbacks),
                "planner_trace": planner_trace,
            }

        if len(steps) >= max_goal_steps:
            raise RuntimeError(
                f"Objetivo não concluído após o limite de {max_goal_steps} etapas físicas."
            )

        result = _execute_one(executor, plan)
        verified = result.get("verified")
        steps.append(
            {
                "step": len(steps) + 1,
                "action": plan.action,
                "target": plan.target,
                "verified": verified,
                "observation": _compact_observation(result),
            }
        )

        if verified is False:
            raise RuntimeError(
                f"A etapa {len(steps)} ({plan.action}) não foi verificada; o objetivo não será marcado como concluído."
            )

        followup = _goal_followup_prompt(objective, steps)
        plan = planner.plan(followup)

        if len(steps) >= max_goal_steps and plan.action != "finish":
            raise RuntimeError(
                f"Objetivo não concluído após o limite de {max_goal_steps} etapas físicas."
            )


def execute_command(
    executor: ActionExecutor,
    command: str,
    *,
    planner: Planner | None = None,
    max_goal_steps: int = 8,
) -> dict[str, Any]:
    active_planner = planner or DeterministicPlanner()
    plan = active_planner.plan(command)

    provider_names = getattr(active_planner, "provider_names", ())
    first_provider = getattr(active_planner, "last_provider", None)
    if provider_names and first_provider != "deterministic":
        return _execute_goal_loop(
            executor,
            command,
            active_planner,
            plan,
            max_goal_steps=max_goal_steps,
        )

    result = _execute_one(executor, plan)
    snapshot = _planner_snapshot(active_planner)
    if snapshot["provider"]:
        result["planner_provider"] = snapshot["provider"]
    if snapshot["route"]:
        result["planner_route"] = snapshot["route"]
    if snapshot["fallbacks"]:
        result["planner_fallbacks"] = snapshot["fallbacks"]
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
    planner = build_planner(cfg)

    planner_names = getattr(planner, "provider_names", ())
    planner_detail = (
        f"multi provedores={','.join(planner_names)}" if planner_names else "determinístico"
    )
    log(
        f"Robô iniciando agente={cfg.agent_id} desktop={'habilitado' if cfg.desktop_enabled else 'desabilitado'} "
        f"planner={planner_detail} goal-max-steps={cfg.goal_max_steps}"
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
                                result = execute_command(
                                    executor,
                                    task.command,
                                    planner=planner,
                                    max_goal_steps=cfg.goal_max_steps,
                                )
                                payload = {
                                    "lease_token": task.lease_token,
                                    "ok": True,
                                    "result": result,
                                }
                                provider = result.get("planner_provider")
                                route = result.get("planner_route")
                                planner_suffix = (
                                    f" planner={provider} rota={route}" if provider else ""
                                )
                                goal_suffix = (
                                    f" etapas={len(result.get('steps', []))} objetivo=concluido"
                                    if result.get("goal_completed")
                                    else ""
                                )
                                log(
                                    f"Tarefa executada id={task.id} resultado=sucesso{planner_suffix}{goal_suffix}"
                                )
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
