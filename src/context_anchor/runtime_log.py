from __future__ import annotations

from datetime import datetime
from pathlib import Path


DEFAULT_LOG_DIR = Path("runtime/logs")
_ALLOWED_COMPONENTS = {"panel", "central", "robot"}


def _component_name(component: str) -> str:
    normalized = component.strip().lower()
    if normalized not in _ALLOWED_COMPONENTS:
        raise ValueError(f"Componente de log inválido: {component}")
    return normalized


def runtime_log_path(component: str, log_dir: Path | str = DEFAULT_LOG_DIR) -> Path:
    return Path(log_dir) / f"{_component_name(component)}.log"


def write_runtime_log(
    component: str,
    message: str,
    *,
    level: str = "INFO",
    log_dir: Path | str = DEFAULT_LOG_DIR,
) -> None:
    path = runtime_log_path(component, log_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    safe_level = level.strip().upper()[:12] or "INFO"
    safe_message = " ".join(str(message).replace("\n", " ").split())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {safe_level} {safe_message}\n")


def tail_runtime_log(
    component: str,
    *,
    lines: int = 80,
    log_dir: Path | str = DEFAULT_LOG_DIR,
) -> list[str]:
    path = runtime_log_path(component, log_dir)
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []
    return content[-max(1, lines) :]
