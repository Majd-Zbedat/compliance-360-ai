"""Orchestrator settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class OrchestratorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "orchestrator"
    rag_service_url: str = "http://localhost:8001"
    doc_analyzer_service_url: str = "http://localhost:8002"
    guardrails_service_url: str = "http://localhost:8003"
    langgraph_agent_service_url: str = "http://localhost:8004"
    database_url: str = "sqlite:///./data/auditor.db"
    request_timeout_s: float = 120.0

    @property
    def sqlite_dir(self) -> Path:
        if self.database_url.startswith("sqlite"):
            return Path(self.database_url.split("///", 1)[-1]).parent.resolve()
        return Path(".")


settings = OrchestratorSettings()
