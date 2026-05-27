"""LangGraph agent service settings."""

from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "langgraph-agent-service"
    rag_service_url: str = "http://localhost:8001"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    enable_llm_reasoning: bool = True
    top_k_per_clause: int = 3


settings = AgentSettings()
