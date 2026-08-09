from __future__ import annotations

from pathlib import Path
from typing import Literal

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

    # Planner. Deterministic remains the safe default until local credentials are configured.
    planner_mode: Literal["deterministic", "multi"] = "deterministic"
    planner_timeout_seconds: float = Field(default=25.0, ge=3.0, le=120.0)
    planner_cooldown_seconds: float = Field(default=30.0, ge=1.0, le=3600.0)

    # Z.AI / GLM
    zai_api_key: str | None = None
    zai_model: str = "glm-4.7-flash"

    # Cloudflare Workers AI
    cloudflare_api_token: str | None = None
    cloudflare_account_id: str | None = None
    cloudflare_model: str = "@cf/meta/llama-3.1-8b-instruct-fast"
    cloudflare_rpm_limit: int = Field(default=300, ge=1, le=10000)

    # Google Gemini
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_rpm_limit: int = Field(default=20, ge=1, le=10000)


class DashboardSettings(BaseAppSettings):
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = Field(default=8765, ge=1024, le=65535)
    central_pid_path: Path = Path("runtime/central.pid")
    log_dir: Path = Path("runtime/logs")
    env_path: Path = Path(".env")
