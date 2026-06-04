"""Orchestrator settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _PROJECT_ROOT / ".env"


class OrchestratorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        extra="ignore",
    )

    service_name: str = "orchestrator"
    rag_service_url: str = "http://localhost:8001"
    doc_analyzer_service_url: str = "http://localhost:8002"
    guardrails_service_url: str = "http://localhost:8003"
    langgraph_agent_service_url: str = "http://localhost:8004"
    database_url: str = "sqlite:///./data/auditor.db"
    request_timeout_s: float = 120.0
    # When set, POST /audits forwards to n8n instead of the in-process Python pipeline.
    # Default 9090 matches common Docker mapping (host 9090 → n8n 5678).
    n8n_webhook_url: str = "http://localhost:9090/webhook/compliance-audit"
    n8n_request_timeout_s: float = 180.0
    # When n8n returns HTTP 200 with an empty body, run the in-process Python pipeline.
    n8n_fallback_to_python: bool = True
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "models/gemini-2.5-flash"

    @property
    def enable_llm_reasoning(self) -> bool:
        return bool(self.openai_api_key or self.gemini_api_key)

    @property
    def sqlite_dir(self) -> Path:
        if self.database_url.startswith("sqlite"):
            return Path(self.database_url.split("///", 1)[-1]).parent.resolve()
        return Path(".")


settings = OrchestratorSettings()
