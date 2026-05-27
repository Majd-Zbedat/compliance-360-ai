"""Guardrails service settings."""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class GuardrailsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "guardrails-service"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    enable_llm_critic: bool = True
    min_input_chars: int = 80


settings = GuardrailsSettings()
