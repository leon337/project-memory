from __future__ import annotations

import argparse
import json
import os
import signal
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class EmergencyStopTriggered(RuntimeError):
    pass


class EmergencyStop:
    def __init__(self, stop_path: Path, pid_path: Path) -> None:
        self.stop_path = Path(stop_path)
        self.pid_path = Path(pid_path)

    def is_triggered(self) -> bool:
        return self.stop_path.exists()

    def assert_not_triggered(self) -> None:
        if self.is_triggered():
            raise EmergencyStopTriggered(
                f"Emergency stop ativo em {self.stop_path}. Limpe-o antes de reiniciar o agente."
            )

    def trigger(self, *, reason: str = "manual", terminate_process: bool = True) -> dict[str, object]:
        self.stop_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        self.stop_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        terminated_pid: int | None = None
        if terminate_process:
            pid = self._read_pid()
            if pid is not None and pid != os.getpid():
                try:
                    os.kill(pid, signal.SIGTERM)
                    terminated_pid = pid
                except ProcessLookupError:
                    self.pid_path.unlink(missing_ok=True)
                except PermissionError:
                    pass

        return {
            "active": True,
            "stop_path": str(self.stop_path),
            "terminated_pid": terminated_pid,
        }

    def clear(self) -> dict[str, object]:
        self.stop_path.unlink(missing_ok=True)
        return {"active": False, "stop_path": str(self.stop_path)}

    def status(self) -> dict[str, object]:
        return {
            "active": self.is_triggered(),
            "stop_path": str(self.stop_path),
            "agent_pid": self._read_pid(),
        }

    def _read_pid(self) -> int | None:
        try:
            raw = self.pid_path.read_text(encoding="utf-8").strip()
            return int(raw)
        except (FileNotFoundError, ValueError):
            return None

    @contextmanager
    def register_agent_process(self) -> Iterator[None]:
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        self.pid_path.write_text(str(os.getpid()), encoding="utf-8")
        try:
            yield
        finally:
            try:
                if self._read_pid() == os.getpid():
                    self.pid_path.unlink(missing_ok=True)
            except OSError:
                pass


def _default_stop() -> EmergencyStop:
    from .config import LocalAgentSettings

    cfg = LocalAgentSettings()
    return EmergencyStop(cfg.emergency_stop_path, cfg.agent_pid_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Emergency stop local do Context Anchor")
    parser.add_argument("command", choices=("trigger", "clear", "status"))
    parser.add_argument("--reason", default="manual")
    args = parser.parse_args()

    stop = _default_stop()
    if args.command == "trigger":
        result = stop.trigger(reason=args.reason, terminate_process=True)
    elif args.command == "clear":
        result = stop.clear()
    else:
        result = stop.status()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
