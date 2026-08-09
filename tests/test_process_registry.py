import json

import context_anchor.process_registry as registry


def _write_record(path, *, pid=123, start_ticks=456):
    path.write_text(json.dumps({"pid": pid, "start_ticks": start_ticks}), encoding="utf-8")


def test_record_is_alive_rejects_zombie(tmp_path, monkeypatch):
    record_path = tmp_path / "robot.pid"
    _write_record(record_path)
    monkeypatch.setattr(registry, "linux_start_ticks", lambda pid: 456)
    monkeypatch.setattr(registry, "linux_process_state", lambda pid: "Z")

    assert registry.record_is_alive(record_path) is False


def test_record_is_alive_accepts_matching_live_process(tmp_path, monkeypatch):
    record_path = tmp_path / "robot.pid"
    _write_record(record_path)
    monkeypatch.setattr(registry, "linux_start_ticks", lambda pid: 456)
    monkeypatch.setattr(registry, "linux_process_state", lambda pid: "S")

    assert registry.record_is_alive(record_path) is True


def test_terminate_registered_process_cleans_zombie_record(tmp_path, monkeypatch):
    record_path = tmp_path / "robot.pid"
    _write_record(record_path)
    monkeypatch.setattr(registry, "linux_start_ticks", lambda pid: 456)
    monkeypatch.setattr(registry, "linux_process_state", lambda pid: "Z")

    result = registry.terminate_registered_process(record_path)

    assert result["stopped"] is False
    assert result["reason"] == "processo já encerrado"
    assert record_path.exists() is False
