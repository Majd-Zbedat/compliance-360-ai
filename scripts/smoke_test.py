"""End-to-end smoke test for the Compliance 360 core loop.

Validates the entire pipeline without requiring all five HTTP services to be
running. It exercises the *same code paths* the running services would,
just dispatched in-process:

  1. Seed the regulatory corpus into ChromaDB.
  2. Segment the sample contract via the doc-analyzer's segmenter.
  3. Run the guardrails-service input check on the raw text.
  4. Run the LangGraph agent (planner -> tool_exec -> synthesiser) with
     `rag_search` rebound to call ChromaDB directly (no HTTP).
  5. Run the guardrails-service output check on the synthesised report.
  6. Assert the audit contains at least one High, one Medium, one Low
     finding, each citing a real seeded regulatory clause.

Usage:
    python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Force a clean, throwaway ChromaDB so the smoke test never collides with
# whatever the dev environment is using.
_tmp_chroma = tempfile.mkdtemp(prefix="smoke-chroma-")
import os

os.environ["CHROMA_PERSIST_DIR"] = _tmp_chroma
os.environ["EMBEDDING_MODEL"] = "__force_fallback__"

# Now import services -----------------------------------------------------
from services.doc_analyzer_service.app.segmenter import segment  # noqa: E402
from services.guardrails_service.app.rails import check_input, check_output  # noqa: E402
from services.langgraph_agent_service.app import graph as agent_graph  # noqa: E402
from services.langgraph_agent_service.app.schemas import ClauseInput  # noqa: E402
from services.rag_service.app.store import get_store  # noqa: E402

CORPUS_DIR = ROOT / "data" / "regulatory_corpus"
SAMPLE = (ROOT / "data" / "sample_contracts" / "sample_msa.txt").read_text(encoding="utf-8")


def seed_corpus() -> int:
    store = get_store()
    store.reset_regulations()
    ids, docs, metas = [], [], []
    for path in sorted(CORPUS_DIR.glob("*.json")):
        for it in json.loads(path.read_text(encoding="utf-8")):
            ids.append(it["id"])
            docs.append(it["text"])
            metas.append(
                {
                    "source": it["source"],
                    "article": it["article"],
                    "title": it.get("title") or "",
                    "tags": ",".join(it.get("tags", [])),
                }
            )
    store.upsert_regulations(ids=ids, documents=docs, metadatas=metas)
    return store.regulations_count()


async def rag_search_inproc(clause_text: str, top_k: int = 3, sources=None):
    """Rebind for the agent: query Chroma directly instead of HTTP."""
    store = get_store()
    rows = store.query_regulations(text=clause_text, top_k=top_k, sources=sources)
    return [
        {
            "id": r["id"],
            "source": (r.get("metadata") or {}).get("source"),
            "article": (r.get("metadata") or {}).get("article"),
            "text": r.get("text", ""),
            "score": r.get("score") or 0.0,
        }
        for r in rows
    ]


async def run() -> None:
    print("[smoke] seeding regulatory corpus into temp ChromaDB ...")
    n = seed_corpus()
    print(f"[smoke] seeded {n} regulatory clauses")

    print("[smoke] segmenting sample contract ...")
    clause_dicts = segment(SAMPLE, contract_id="ctr-smoke", min_chars=40)
    print(f"[smoke] {len(clause_dicts)} clauses extracted")
    assert len(clause_dicts) >= 5, f"expected >=5 clauses, got {len(clause_dicts)}"

    print("[smoke] running input guardrail ...")
    input_check = check_input(SAMPLE)
    print(f"        passed={input_check['passed']}")
    assert input_check["passed"], "input guardrail should accept a real contract"

    # Rebind the agent's `rag_search` so it stays in-process.
    agent_graph.rag_search = rag_search_inproc

    clauses = [ClauseInput(**c) for c in clause_dicts]
    print("[smoke] running LangGraph agent ...")
    state = await agent_graph.run_audit(
        audit_id="aud-smoke",
        contract_id="ctr-smoke",
        clauses=clauses,
    )
    print(f"        status={state.status} overall_risk={state.overall_risk}")
    print(f"        findings={len(state.findings)}  trace_nodes={len(state.trace)}")

    print("[smoke] running output guardrail on synthesised report ...")
    output_check = check_output(state.report_markdown)
    safe_report = output_check.get("safe_text") or state.report_markdown
    print(
        f"        matched_rules={output_check['matched_rules']} "
        f"report_chars={len(safe_report)}"
    )

    counts = {"High": 0, "Medium": 0, "Low": 0}
    cited = 0
    for f in state.findings:
        counts[f.risk] = counts.get(f.risk, 0) + 1
        if f.matched_regulatory_clause_id:
            cited += 1
    print(f"[smoke] risk counts: {counts}")
    print(f"[smoke] {cited}/{len(state.findings)} findings carry a regulatory citation")

    # Acceptance criteria (plan section 8) ---------------------------------
    assert counts["High"] >= 1, "expected at least 1 High-risk finding"
    assert counts["Medium"] >= 1, "expected at least 1 Medium-risk finding"
    assert counts["Low"] >= 1, "expected at least 1 Low-risk finding"
    assert cited >= 3, "expected at least 3 findings to cite a seeded regulatory clause"

    print()
    print("=" * 70)
    print("SMOKE TEST PASSED")
    print("=" * 70)
    print(safe_report[:1500])


if __name__ == "__main__":
    asyncio.run(run())
