"""Smoke test for the RAG service.

Uses the hashing-fallback embedder so it runs without downloading models.
"""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    tmpdir = tempfile.mkdtemp(prefix="rag-test-")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", tmpdir)
    monkeypatch.setenv("EMBEDDING_MODEL", "__force_fallback__")

    # Force fresh import so settings re-read env vars.
    import importlib
    import services.rag_service.app.config as cfg
    import services.rag_service.app.embeddings as emb
    import services.rag_service.app.store as store_mod
    import services.rag_service.app.main as main_mod

    for mod in [cfg, emb, store_mod, main_mod]:
        importlib.reload(mod)
    store_mod._store = None

    yield TestClient(main_mod.app)


def test_upsert_then_query(client):
    payload = {
        "reset": True,
        "items": [
            {
                "id": "GDPR-5-1-c",
                "source": "GDPR",
                "article": "Art. 5(1)(c)",
                "title": "Data minimisation",
                "text": "Personal data shall be adequate, relevant and limited to what is necessary.",
                "tags": ["data_processing"],
            },
            {
                "id": "ISO-A8-1-3",
                "source": "ISO27001",
                "article": "A.8.1.3",
                "title": "Acceptable use of assets",
                "text": "Rules for the acceptable use of information assets shall be identified.",
                "tags": ["access_control"],
            },
        ],
    }
    r = client.post("/upsert", json=payload)
    assert r.status_code == 200
    assert r.json()["upserted"] == 2

    q = client.post(
        "/query",
        json={"text": "We collect every field about the customer for marketing.", "top_k": 2},
    )
    assert q.status_code == 200
    data = q.json()
    assert len(data["matches"]) == 2
    assert "GDPR" in data["insight"] or "ISO27001" in data["insight"]
