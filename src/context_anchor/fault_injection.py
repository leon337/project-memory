from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DesktopSettings


CHECKPOINTS = (
    "after_prepare",
    "after_in_flight",
    "after_backend",
    "after_executed",
    "before_ack",
    "after_ack",
)
FAULT_EXIT_CODE = 86


class FaultInjectionError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)


class FaultInjectionController:
    """Local-only, one-shot crash injection for physical recovery smoke tests.

    Arming is persisted in a local runtime file, never through the Central or Panel.
    A matching checkpoint atomically consumes the arm before terminating the local
    agent, so restarting the agent cannot loop on the same injected crash.
    """

    def __init__(
        self,
        arm_path: Path,
        last_event_path: Path,
        *,
        terminator: Callable[[int], Any] | None = None,
    ) -> None:
        self.arm_path = Path(arm_path)
        self.last_event_path = Path(last_event_path)
        self._terminator = terminator or os._exit

    def arm(self, checkpoint: str) -> dict[str, Any]:
        if checkpoint not in CHECKPOINTS:
            raise FaultInjectionError(
                f"Checkpoint inválido: {checkpoint}. Válidos: {', '.join(CHECKPOINTS)}"
            )
        payload = {
            "version": 1,
            "checkpoint": checkpoint,
            "armed_at": _utc_now(),
        }
        _atomic_json_write(self.arm_path, payload)
        return payload

    def clear(self) -> bool:
        try:
            self.arm_path.unlink()
            return True
        except FileNotFoundError:
            return False

    def status(self) -> dict[str, Any] | None:
        try:
            raw = json.loads(self.arm_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise FaultInjectionError(f"Arquivo de fault injection inválido: {exc}") from exc
        if not isinstance(raw, dict):
            raise FaultInjectionError("Arquivo de fault injection precisa conter um objeto JSON.")
        checkpoint = raw.get("checkpoint")
        if checkpoint not in CHECKPOINTS:
            raise FaultInjectionError("Arquivo de fault injection contém checkpoint desconhecido.")
        return raw

    def checkpoint(
        self,
        checkpoint: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> bool:
        if checkpoint not in CHECKPOINTS:
            raise FaultInjectionError(f"Checkpoint de código desconhecido: {checkpoint}")

        armed = self.status()
        if armed is None or armed.get("checkpoint") != checkpoint:
            return False

        consumed = self.arm_path.with_name(
            f".{self.arm_path.name}.{os.getpid()}.consumed"
        )
        try:
            os.replace(self.arm_path, consumed)
        except FileNotFoundError:
            return False

        event_context = dict(context or {})
        # Only technical identifiers may be persisted. Never include command/target text.
        safe_context = {
            key: event_context[key]
            for key in ("task_id", "action_key", "action_name", "status")
            if key in event_context
        }
        event = {
            "version": 1,
            "checkpoint": checkpoint,
            "triggered_at": _utc_now(),
            "pid": os.getpid(),
            "exit_code": FAULT_EXIT_CODE,
            "context": safe_context,
        }
        _atomic_json_write(self.last_event_path, event)
        try:
            consumed.unlink()
        except FileNotFoundError:
            pass

        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            self._terminator(FAULT_EXIT_CODE)
        return True


def _controller_from_settings() -> FaultInjectionController:
    settings = DesktopSettings()
    return FaultInjectionController(
        settings.fault_injection_path,
        settings.fault_injection_last_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="falha-robo",
        description="Arma uma falha física controlada e one-shot no processo local do Robô.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("listar", help="Lista checkpoints disponíveis.")
    sub.add_parser("status", help="Mostra o checkpoint atualmente armado.")
    sub.add_parser("limpar", help="Remove um checkpoint armado sem executá-lo.")
    arm_parser = sub.add_parser("armar", help="Arma um checkpoint one-shot.")
    arm_parser.add_argument("checkpoint", choices=CHECKPOINTS)
    args = parser.parse_args()

    controller = _controller_from_settings()
    if args.command == "listar":
        print("\n".join(CHECKPOINTS))
        return
    if args.command == "status":
        status = controller.status()
        if status is None:
            print("FAULT INJECTION: DESARMADO")
        else:
            print(f"FAULT INJECTION: ARMADO em {status['checkpoint']}")
        return
    if args.command == "limpar":
        removed = controller.clear()
        print("FAULT INJECTION: DESARMADO" if removed else "FAULT INJECTION: JÁ ESTAVA DESARMADO")
        return
    if args.command == "armar":
        payload = controller.arm(args.checkpoint)
        print(
            "FAULT INJECTION: ARMADO ONE-SHOT\n"
            f"checkpoint: {payload['checkpoint']}\n"
            "Somente o processo local do Robô será encerrado quando atingir esse ponto."
        )
        return

    raise SystemExit(2)


__all__ = [
    "CHECKPOINTS",
    "FAULT_EXIT_CODE",
    "FaultInjectionController",
    "FaultInjectionError",
    "main",
]


if __name__ == "__main__":
    main()
