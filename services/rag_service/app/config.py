"""Runtime configuration for the RAG service."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class RagSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    chroma_persist_dir: str = "./data/chroma"
    chroma_regulations_collection: str = "regulations"
    chroma_contracts_collection: str = "contracts"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k_default: int = 3
    service_name: str = "rag-service"

    @property
    def persist_path(self) -> Path:
        return Path(self.chroma_persist_dir).resolve()


settings = RagSettings()
