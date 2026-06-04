"""ChromaDB store wrapper for regulatory + contract collections."""

from __future__ import annotations

from typing import Any, Iterable, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from .config import settings
from .embeddings import build_embedder


class _ChromaCompatibleEmbedder:
    """Adapter that satisfies Chroma's `EmbeddingFunction` protocol."""

    def __init__(self, fn):
        self._fn = fn

    def name(self) -> str:
        return getattr(self._fn, "name", "custom")

    def __call__(self, input):
        return self._fn(input)


class VectorStore:
    """Thin facade over ChromaDB persistent client."""

    def __init__(self):
        settings.persist_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(settings.persist_path),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
        self._embedder = _ChromaCompatibleEmbedder(build_embedder())
        self.embedder_name = getattr(self._embedder._fn, "name", "custom")

        self.regulations = self._client.get_or_create_collection(
            name=settings.chroma_regulations_collection,
            embedding_function=self._embedder,
            metadata={"hnsw:space": "cosine"},
        )
        self.contracts = self._client.get_or_create_collection(
            name=settings.chroma_contracts_collection,
            embedding_function=self._embedder,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_regulations(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self.regulations.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def upsert_contract_chunks(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self.contracts.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def query_regulations(
        self,
        text: str,
        top_k: int = 3,
        sources: Optional[Iterable[str]] = None,
    ) -> list[dict[str, Any]]:
        where = None
        if sources:
            sources_list = list(sources)
            if len(sources_list) == 1:
                where = {"source": sources_list[0]}
            elif sources_list:
                where = {"source": {"$in": sources_list}}
        result = self.regulations.query(
            query_texts=[text],
            n_results=top_k,
            where=where,
        )
        return _flatten_query(result)

    def query_contracts(
        self,
        text: str,
        top_k: int = 5,
        *,
        category: Optional[str] = None,
        audit_id: Optional[str] = None,
        include_portfolio: bool = True,
    ) -> list[dict[str, Any]]:
        """Vector search over indexed portfolio rows and uploaded audit clauses."""
        if self.contracts.count() == 0:
            return []

        merged: list[dict[str, Any]] = []
        seen: set[str] = set()

        def _run(where: Optional[dict]) -> None:
            nonlocal merged
            if len(merged) >= top_k:
                return
            n = min(top_k, top_k - len(merged) + 2)
            result = self.contracts.query(
                query_texts=[text],
                n_results=n,
                where=where,
            )
            for row in _flatten_query(result):
                rid = row["id"]
                if rid in seen:
                    continue
                seen.add(rid)
                merged.append(row)
                if len(merged) >= top_k:
                    break

        if audit_id:
            _run({"audit_id": audit_id})
        if include_portfolio:
            if category in ("bank", "cybersecurity", "ai"):
                _run({"doc_type": "portfolio", "category": category})
            else:
                _run({"doc_type": "portfolio"})
        if not audit_id and not include_portfolio:
            _run(None)

        merged.sort(key=lambda r: float(r.get("score") or 0.0), reverse=True)
        return merged[:top_k]

    def contracts_count(self) -> int:
        return self.contracts.count()

    def delete_audit_contracts(self, audit_id: str) -> None:
        """Remove prior chunks for an audit before re-indexing."""
        try:
            self.contracts.delete(where={"audit_id": audit_id})
        except Exception:
            pass

    def regulations_count(self) -> int:
        return self.regulations.count()

    def reset_regulations(self) -> None:
        try:
            self._client.delete_collection(settings.chroma_regulations_collection)
        except Exception:
            pass
        self.regulations = self._client.get_or_create_collection(
            name=settings.chroma_regulations_collection,
            embedding_function=self._embedder,
            metadata={"hnsw:space": "cosine"},
        )


def _flatten_query(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Chroma returns parallel arrays-of-arrays; flatten to one query."""
    if not result.get("ids"):
        return []
    ids = result["ids"][0]
    docs = result.get("documents", [[]])[0] or [""] * len(ids)
    metas = result.get("metadatas", [[]])[0] or [{}] * len(ids)
    dists = result.get("distances", [[]])[0] or [None] * len(ids)
    out = []
    for i, doc_id in enumerate(ids):
        out.append(
            {
                "id": doc_id,
                "text": docs[i],
                "metadata": metas[i] or {},
                "distance": dists[i],
                "score": None if dists[i] is None else max(0.0, 1.0 - float(dists[i])),
            }
        )
    return out


_store: Optional[VectorStore] = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
