"""Tools the LangGraph agent can call.

Currently only `rag_search` is wired (per the core-loop scope). Tool
descriptions are kept first-class because the PDF's prompt-engineering log
treats them as a graded surface (Surface #2: agent tool descriptions).
"""

from __future__ import annotations

import httpx

from .config import settings


# Tool descriptions - these strings *are* the prompt engineering surface
# referenced by the prompt log. Iterate carefully.
RAG_TOOL_DESCRIPTION = (
    "rag_search(clause_text: str, top_k: int = 3, sources: list[str] | None = None) -> "
    "list[RetrievedClause]. "
    "Use this to find the most relevant regulatory clauses (GDPR / ISO 27001 / Local Law) "
    "for a given contract clause. ALWAYS call this before assigning a verdict, and "
    "ALWAYS cite the returned regulatory id and article in your justification. "
    "Do not invent regulatory references that the tool did not return."
)


async def rag_search(
    clause_text: str,
    top_k: int = 3,
    sources: list[str] | None = None,
) -> list[dict]:
    payload = {"text": clause_text, "top_k": top_k}
    if sources:
        payload["sources"] = sources
    async with httpx.AsyncClient(timeout=20.0) as client:
        url = settings.rag_service_url.rstrip("/") + "/query"
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json().get("matches", [])
