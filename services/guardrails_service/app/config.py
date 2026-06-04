"""Guardrails service settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _PROJECT_ROOT / ".env"


class GuardrailsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else ".env",
        extra="ignore",
    )

    service_name: str = "guardrails-service"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "models/gemini-2.5-flash"
    enable_llm_critic: bool = True
    min_input_chars: int = 80

    @property
    def has_llm(self) -> bool:
        return bool(self.gemini_api_key or self.openai_api_key)


settings = GuardrailsSettings()
