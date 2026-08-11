from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from .action_journal import ActionReplayBlocked
from .actions import ActionExecutor
from .capabilities import CapabilityResolver
from .config import DashboardSettings, LocalAgentSettings
from .desktop import DesktopFailsafeTriggered
from .emergency_stop import EmergencyStop, EmergencyStopTriggered
from .fault_injection import FaultInjectionController
from .goal_execution import GoalExecutionFailed, execute_goal
from .goal_interpreter import SemanticGoalInterpreter
from .lease import (
    DeferredSessionContext,
    LeaseGuardedExecutor,
    LeaseHeartbeat,
    LeaseOwnershipLost,
    is_safety_interrupt,
)
from .planner import (
    DeterministicPlanner,
    MultiProviderPlanner,
    Planner,
    ProviderCandidate,
)
from .providers import CloudflareWorkersAIProvider, GeminiProvider, ZAIProvider
from .redaction import redact_exception
from .reliable_desktop import StableFocusDesktopBackend
from .runtime_log import write_runtime_log
from .schemas import AgentTask
from .session_context import SessionContext


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


def execute_command(
    executor: ActionExecutor,
    command: str,
    *,
    planner: Planner | None = None,
    max_goal_steps: int = 8,
    task_id: str | None = None,
    session_context: SessionContext | DeferredSessionContext | None = None,
    capability_resolver: CapabilityResolver | None = None,
    interpreter: SemanticGoalInterpreter | None = None,
) -> dict[str, Any]:
    return execute_goal(
        executor,
        command,
        planner=planner,
        max_goal_steps=max_goal_steps,
        task_id=task_id,
        session_context=session_context,
        capability_resolver=capability_resolver,
        interpreter=interpreter,
    )


def _submit_task_result(
    client: httpx.Client,
    task_id: str,
    payload: dict[str, Any],
    deferred_context: DeferredSessionContext,
) -> dict[str, Any]:
    """Submit the result and publish context only after Central acknowledges it."""

    try:
        finish = client.post(f"/api/agent/tasks/{task_id}/result", json=payload)
        finish.raise_for_status()
        finish_payload = finish.json()
    except Exception:
        deferred_context.discard()
        raise
    if payload["ok"] is True and finish_payload.get("status") == "succeeded":
        deferred_context.commit()
    else:
        deferred_context.discard()
    return finish_payload


def _submit_task_result_preserving_safety(
    client: httpx.Client,
    task_id: str,
    payload: dict[str, Any],
    deferred_context: DeferredSessionContext,
    safety_interrupt: Exception | None,
) -> dict[str, Any]:
    """Never let a result transport error replace an active safety interrupt."""

    try:
        return _submit_task_result(client, task_id, payload, deferred_context)
    finally:
        if safety_interrupt is not None:
            raise safety_interrupt


def run() -> None:
    cfg = LocalAgentSettings()
    dashboard_cfg = DashboardSettings()
    headers = {"Authorization": f"Bearer {cfg.agent_token}"}
    stop = EmergencyStop(cfg.emergency_stop_path, cfg.agent_pid_path)
    # Defaults keep older test doubles and local configs compatible while the
    # real LocalAgentSettings exposes these paths explicitly.
    fault_injection = FaultInjectionController(
        Path(getattr(cfg, "fault_injection_path", "runtime/fault_injection.json")),
        Path(
            getattr(
                cfg,
                "fault_injection_last_path",
                "runtime/fault_injection_last.json",
            )
        ),
    )

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
        desktop_backend=StableFocusDesktopBackend(input_guard=stop.assert_not_triggered),
        screenshot_dir=cfg.screenshot_dir,
        emergency_stop=stop,
    )
    planner = build_planner(cfg)
    session_context = SessionContext(cfg.session_context_path)

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

                            deferred_context = DeferredSessionContext(session_context)
                            safety_interrupt: Exception | None = None
                            try:
                                with LeaseHeartbeat(
                                    base_url=cfg.control_plane_url,
                                    headers=headers,
                                    task_id=task.id,
                                    lease_token=task.lease_token,
                                    lease_seconds=task.lease_seconds,
                                ) as lease:
                                    leased_executor = LeaseGuardedExecutor(
                                        executor,
                                        lease,
                                        fault_injection=fault_injection,
                                    )
                                    try:
                                        result = execute_command(
                                            leased_executor,
                                            task.command,
                                            planner=planner,
                                            max_goal_steps=cfg.goal_max_steps,
                                            task_id=task.id,
                                            session_context=deferred_context,
                                        )
                                        if result.get("status") != "succeeded" or not result.get(
                                            "goal_completed"
                                        ):
                                            raise RuntimeError(
                                                "Goal Runtime retornou sem verdict succeeded comprovado."
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
                                            f"Tarefa executada id={task.id} "
                                            f"resultado=sucesso{planner_suffix}{goal_suffix}"
                                        )
                                    except GoalExecutionFailed as exc:
                                        safe_error = redact_exception(exc)
                                        payload = {
                                            "lease_token": task.lease_token,
                                            "ok": False,
                                            "result": exc.result,
                                            "error": safe_error,
                                        }
                                        metrics = exc.result.get("metrics", {})
                                        log(
                                            f"Tarefa incompleta id={task.id} "
                                            f"status={metrics.get('status', 'failed')} "
                                            f"etapas={metrics.get('steps', 0)} motivo={safe_error}",
                                            level="ERROR",
                                        )
                                    except LeaseOwnershipLost:
                                        raise
                                    except ActionReplayBlocked as exc:
                                        safe_error = redact_exception(exc)
                                        payload = {
                                            "lease_token": task.lease_token,
                                            "ok": False,
                                            "error": safe_error,
                                        }
                                        log(
                                            f"Replay físico bloqueado id={task.id} "
                                            f"action_key={exc.action_key} state={exc.state}",
                                            level="WARN",
                                        )
                                    except (
                                        EmergencyStopTriggered,
                                        DesktopFailsafeTriggered,
                                    ) as exc:
                                        safe_error = redact_exception(exc)
                                        payload = {
                                            "lease_token": task.lease_token,
                                            "ok": False,
                                            "error": safe_error,
                                        }
                                        safety_interrupt = exc
                                        log(
                                            f"Tarefa interrompida id={task.id} por controle de segurança "
                                            f"tipo={type(exc).__name__}",
                                            level="WARN",
                                        )
                                    except Exception as exc:
                                        safe_error = redact_exception(exc)
                                        payload = {
                                            "lease_token": task.lease_token,
                                            "ok": False,
                                            "error": safe_error,
                                        }
                                        if is_safety_interrupt(exc):
                                            safety_interrupt = exc
                                            log(
                                                f"Tarefa interrompida id={task.id} "
                                                "por controle de segurança "
                                                f"tipo={type(exc).__name__}",
                                                level="WARN",
                                            )
                                        else:
                                            log(
                                                f"Tarefa falhou id={task.id} "
                                                f"erro={safe_error}",
                                                level="ERROR",
                                            )

                                    # A final result can only be sent after one last
                                    # ownership check. The result endpoint performs
                                    # the definitive atomic token/expiry validation.
                                    lease.assert_owned()
                            except LeaseOwnershipLost as exc:
                                deferred_context.discard()
                                if safety_interrupt is not None:
                                    raise safety_interrupt from exc
                                safe_error = redact_exception(exc)
                                log(
                                    f"Tarefa abortada id={task.id}: posse do lease perdida "
                                    f"({safe_error})",
                                    level="WARN",
                                )
                                continue

                            fault_injection.checkpoint(
                                "before_ack",
                                context={"task_id": task.id},
                            )
                            finish_payload = _submit_task_result_preserving_safety(
                                client,
                                task.id,
                                payload,
                                deferred_context,
                                safety_interrupt,
                            )
                            fault_injection.checkpoint(
                                "after_ack",
                                context={
                                    "task_id": task.id,
                                    "status": finish_payload.get("status", "desconhecido"),
                                },
                            )
                            log(
                                f"Resultado enviado id={task.id} "
                                f"status={finish_payload.get('status', 'desconhecido')}"
                            )
                        except httpx.HTTPError as exc:
                            safe_error = redact_exception(exc)
                            log(
                                f"Falha de comunicação com a Central: {safe_error}",
                                level="WARN",
                            )
                            print(f"Falha de comunicação com a Central: {safe_error}")
                            time.sleep(max(cfg.poll_interval_seconds, 3))
                except (
                    KeyboardInterrupt,
                    EmergencyStopTriggered,
                    DesktopFailsafeTriggered,
                ):
                    pass
                except Exception as exc:
                    if not is_safety_interrupt(exc):
                        raise
    finally:
        executor.close()
        log("Robô encerrado")


if __name__ == "__main__":
    run()
