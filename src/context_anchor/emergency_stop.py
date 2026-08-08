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


def _linux_start_ticks(pid: int) -> int | None:
    """Return /proc starttime (field 22) to protect against PID reuse."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        closing = raw.rfind(")")
        if closing < 0:
            return None
        fields_after_comm = raw[closing + 1 :].strip().split()
        return int(fields_after_comm[19])
    except (FileNotFoundError, PermissionError, ValueError, IndexError, OSError):
        return None


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
        process_identity_verified = False
        if terminate_process:
            record = self._read_process_record()
            if record is not None:
                pid = record["pid"]
                expected_ticks = record["start_ticks"]
                current_ticks = _linux_start_ticks(pid)
                process_identity_verified = (
                    expected_ticks is not None
                    and current_ticks is not None
                    and expected_ticks == current_ticks
                )
                if process_identity_verified and pid != os.getpid():
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
            "process_identity_verified": process_identity_verified,
        }

    def clear(self) -> dict[str, object]:
        self.stop_path.unlink(missing_ok=True)
        return {"active": False, "stop_path": str(self.stop_path)}

    def status(self) -> dict[str, object]:
        record = self._read_process_record()
        return {
            "active": self.is_triggered(),
            "stop_path": str(self.stop_path),
            "agent_pid": record["pid"] if record else None,
            "agent_identity_valid": self._record_is_current(record) if record else False,
        }

    def _record_is_current(self, record: dict[str, int | None]) -> bool:
        expected = record.get("start_ticks")
        if expected is None:
            return False
        current = _linux_start_ticks(int(record["pid"]))
        return current is not None and current == expected

    def _read_process_record(self) -> dict[str, int | None] | None:
        try:
            raw = self.pid_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None

        try:
            parsed = json.loads(raw)
            pid = int(parsed["pid"])
            start_ticks_raw = parsed.get("start_ticks")
            start_ticks = int(start_ticks_raw) if start_ticks_raw is not None else None
            return {"pid": pid, "start_ticks": start_ticks}
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            try:
                return {"pid": int(raw), "start_ticks": None}
            except ValueError:
                return None

    @contextmanager
    def register_agent_process(self) -> Iterator[None]:
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid = os.getpid()
        record = {"pid": pid, "start_ticks": _linux_start_ticks(pid)}
        self.pid_path.write_text(json.dumps(record), encoding="utf-8")
        try:
            yield
        finally:
            try:
                current = self._read_process_record()
                if current and current["pid"] == pid and current["start_ticks"] == record["start_ticks"]:
                    self.pid_path.unlink(missing_ok=True)
            except OSError:
                pass


def _default_stop() -> EmergencyStop:
    from .config import EmergencyStopSettings

    cfg = EmergencyStopSettings()
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
