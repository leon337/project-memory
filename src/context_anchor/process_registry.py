from __future__ import annotations

import json
import os
import signal
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def linux_start_ticks(pid: int) -> int | None:
    """Return Linux /proc starttime (field 22) so a reused PID is not trusted."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        closing = raw.rfind(")")
        if closing < 0:
            return None
        fields_after_comm = raw[closing + 1 :].strip().split()
        return int(fields_after_comm[19])
    except (FileNotFoundError, PermissionError, ValueError, IndexError, OSError):
        return None


def write_process_record(path: Path | str, *, pid: int | None = None) -> dict[str, int | None]:
    record_path = Path(path)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    process_id = pid or os.getpid()
    record = {"pid": process_id, "start_ticks": linux_start_ticks(process_id)}
    record_path.write_text(json.dumps(record), encoding="utf-8")
    return record


def read_process_record(path: Path | str) -> dict[str, int | None] | None:
    record_path = Path(path)
    try:
        parsed = json.loads(record_path.read_text(encoding="utf-8"))
        pid = int(parsed["pid"])
        start_ticks_raw = parsed.get("start_ticks")
        start_ticks = int(start_ticks_raw) if start_ticks_raw is not None else None
        return {"pid": pid, "start_ticks": start_ticks}
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError, OSError):
        return None


def record_is_alive(path: Path | str) -> bool:
    record = read_process_record(path)
    if not record or record["start_ticks"] is None:
        return False
    current = linux_start_ticks(int(record["pid"]))
    return current is not None and current == record["start_ticks"]


def terminate_registered_process(
    path: Path | str,
    *,
    sig: signal.Signals = signal.SIGTERM,
) -> dict[str, object]:
    record_path = Path(path)
    record = read_process_record(record_path)
    if not record:
        return {"stopped": False, "reason": "processo não registrado", "pid": None}

    pid = int(record["pid"])
    expected = record["start_ticks"]
    current = linux_start_ticks(pid)
    if expected is None or current is None or current != expected:
        record_path.unlink(missing_ok=True)
        return {"stopped": False, "reason": "registro antigo ou processo já encerrado", "pid": pid}

    if pid == os.getpid():
        return {"stopped": False, "reason": "recusado encerrar o próprio processo", "pid": pid}

    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        record_path.unlink(missing_ok=True)
        return {"stopped": False, "reason": "processo já encerrado", "pid": pid}
    except PermissionError:
        return {"stopped": False, "reason": "sem permissão para encerrar o processo", "pid": pid}

    return {"stopped": True, "reason": "sinal de encerramento enviado", "pid": pid}


@contextmanager
def registered_process(path: Path | str) -> Iterator[dict[str, int | None]]:
    record_path = Path(path)
    record = write_process_record(record_path)
    try:
        yield record
    finally:
        current = read_process_record(record_path)
        if current == record:
            record_path.unlink(missing_ok=True)
