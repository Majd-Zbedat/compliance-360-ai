"""Doc-analyzer service settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class DocAnalyzerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "doc-analyzer-service"
    max_pdf_mb: int = 25
    min_clause_chars: int = 40


settings = DocAnalyzerSettings()
