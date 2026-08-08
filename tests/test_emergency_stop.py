import json
import os
from pathlib import Path

from context_anchor.emergency_stop import EmergencyStop


def test_emergency_stop_trigger_clear_and_status(tmp_path: Path) -> None:
    stop = EmergencyStop(tmp_path / "STOP", tmp_path / "agent.pid")

    assert stop.status()["active"] is False
    result = stop.trigger(reason="test", terminate_process=False)
    assert result["active"] is True
    assert stop.is_triggered() is True

    cleared = stop.clear()
    assert cleared["active"] is False
    assert stop.is_triggered() is False


def test_register_agent_process_writes_identity_and_cleans_pid(tmp_path: Path) -> None:
    pid_path = tmp_path / "agent.pid"
    stop = EmergencyStop(tmp_path / "STOP", pid_path)

    with stop.register_agent_process():
        record = json.loads(pid_path.read_text(encoding="utf-8"))
        assert record["pid"] == os.getpid()
        status = stop.status()
        assert status["agent_pid"] == os.getpid()
        assert status["agent_identity_valid"] is True

    assert pid_path.exists() is False


def test_stale_pid_record_is_never_terminated(tmp_path: Path) -> None:
    pid_path = tmp_path / "agent.pid"
    pid_path.write_text(
        json.dumps({"pid": os.getpid(), "start_ticks": -1}),
        encoding="utf-8",
    )
    stop = EmergencyStop(tmp_path / "STOP", pid_path)

    result = stop.trigger(reason="stale", terminate_process=True)
    assert result["process_identity_verified"] is False
    assert result["terminated_pid"] is None
