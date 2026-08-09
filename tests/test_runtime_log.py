from pathlib import Path

from context_anchor.runtime_log import runtime_log_path, tail_runtime_log, write_runtime_log


def test_runtime_log_writes_timestamped_component_events(tmp_path: Path):
    write_runtime_log("panel", "Painel iniciado", log_dir=tmp_path)
    write_runtime_log("central", "Tarefa criada id=123", log_dir=tmp_path)
    write_runtime_log("robot", "Tarefa executada id=123", level="ERROR", log_dir=tmp_path)

    panel = tail_runtime_log("panel", log_dir=tmp_path)
    central = tail_runtime_log("central", log_dir=tmp_path)
    robot = tail_runtime_log("robot", log_dir=tmp_path)

    assert len(panel) == 1
    assert " INFO Painel iniciado" in panel[0]
    assert "T" in panel[0].split(" ", 1)[0]
    assert "Tarefa criada id=123" in central[0]
    assert " ERROR Tarefa executada id=123" in robot[0]
    assert runtime_log_path("panel", tmp_path) == tmp_path / "panel.log"


def test_runtime_log_rejects_unknown_component(tmp_path: Path):
    try:
        write_runtime_log("qualquer", "teste", log_dir=tmp_path)
    except ValueError as exc:
        assert "Componente de log inválido" in str(exc)
    else:
        raise AssertionError("componentes desconhecidos devem ser recusados")
