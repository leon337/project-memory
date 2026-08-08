from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXT_ANCHOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class ControlPlaneSettings(BaseAppSettings):
    host: str = "127.0.0.1"
    port: int = 8000
    db_path: Path = Path("runtime/context_anchor.db")
    user_token: str = Field(min_length=24)
    agent_token: str = Field(min_length=24)
    task_lease_seconds: int = Field(default=120, ge=30, le=3600)
    task_max_attempts: int = Field(default=3, ge=1, le=10)


class EmergencyStopSettings(BaseAppSettings):
    emergency_stop_path: Path = Path("runtime/EMERGENCY_STOP")
    agent_pid_path: Path = Path("runtime/local_agent.pid")


class DesktopSettings(EmergencyStopSettings):
    desktop_enabled: bool = False
    screenshot_dir: Path = Path("runtime/screenshots")


class LocalAgentSettings(DesktopSettings):
    control_plane_url: str = "http://127.0.0.1:8000"
    agent_id: str = "desktop-principal"
    agent_token: str = Field(min_length=24)
    poll_interval_seconds: float = Field(default=2.0, ge=0.5, le=60)
    browser_headless: bool = False
