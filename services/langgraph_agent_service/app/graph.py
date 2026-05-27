"""LangGraph state machine for the audit reasoning loop.

States and transitions (mirroring the Compliance 360 vision):

    Drafting   -> planner inspects clauses
    Reviewing  -> tool_exec calls rag_search per clause and reasons
    Flagging   -> synthesiser computes overall risk + report
    Done       -> graph END

A graceful no-op path is provided for environments where LangGraph itself
is unavailable, so the FastAPI service still starts and exposes
`/agent/run` for the orchestrator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import settings
from .reasoning import ReasoningInput, reason
from .schemas import AgentTrace, ClauseInput, FindingOut
from .tools import rag_search


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------


@dataclass
class AuditState:
    audit_id: str
    contract_id: str
    clauses: list[ClauseInput]
    status: str = "Drafting"
    findings: list[FindingOut] = field(default_factory=list)
    overall_risk: str = "Unknown"
    report_markdown: str = ""
    trace: list[AgentTrace] = field(default_factory=list)

    def add_trace(self, node: str, detail: str) -> None:
        self.trace.append(AgentTrace(node=node, detail=detail))


# ---------------------------------------------------------------------------
# Node functions (each takes & returns AuditState)
# ---------------------------------------------------------------------------


async def planner_node(state: AuditState) -> AuditState:
    state.status = "Drafting"
    state.add_trace(
        "planner",
        f"Planner inspected {len(state.clauses)} clauses; "
        "will call rag_search per clause then reason per clause.",
    )
    return state


async def tool_exec_node(state: AuditState) -> AuditState:
    state.status = "Reviewing"
    for clause in state.clauses:
        try:
            matches = await rag_search(
                clause_text=clause.text,
                top_k=settings.top_k_per_clause,
            )
        except Exception as exc:
            state.add_trace("tool_exec", f"rag_search failed for {clause.id}: {exc!r}")
            matches = []
        reasoned = reason(
            ReasoningInput(
                clause_id=clause.id,
                clause_text=clause.text,
                clause_type=clause.clause_type,
                matches=matches,
            )
        )
        state.findings.append(
            FindingOut(
                contract_clause_id=clause.id,
                matched_regulatory_clause_id=reasoned.matched_id,
                matched_regulatory_source=reasoned.matched_source,
                matched_regulatory_article=reasoned.matched_article,
                verdict=reasoned.verdict,
                risk=reasoned.risk,
                justification=reasoned.justification,
                confidence=reasoned.confidence,
            )
        )
        state.add_trace(
            "tool_exec",
            f"Clause {clause.id} ({clause.clause_type}) -> {reasoned.verdict}/{reasoned.risk} "
            f"(matches={len(matches)})",
        )
    return state


async def synthesiser_node(state: AuditState) -> AuditState:
    state.status = "Flagging"
    state.overall_risk = _aggregate_risk(state.findings)
    state.report_markdown = _build_report(state)
    state.add_trace(
        "synthesiser",
        f"Synthesised report with {len(state.findings)} findings; overall risk {state.overall_risk}.",
    )
    state.status = "Done"
    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _aggregate_risk(findings: list[FindingOut]) -> str:
    if any(f.risk == "High" for f in findings):
        return "High"
    if any(f.risk == "Medium" for f in findings):
        return "Medium"
    if findings:
        return "Low"
    return "Unknown"


def _build_report(state: AuditState) -> str:
    parts: list[str] = []
    parts.append(f"# Compliance Audit Report")
    parts.append(f"_Audit id_: `{state.audit_id}`  ·  _Overall risk_: **{state.overall_risk}**")
    counts = _counts(state.findings)
    parts.append(
        f"\n**Summary:** {len(state.findings)} findings — "
        f"High: {counts['High']}, Medium: {counts['Medium']}, Low: {counts['Low']}.\n"
    )
    parts.append("## Findings")
    for i, f in enumerate(state.findings, start=1):
        cite = (
            f"{f.matched_regulatory_source} {f.matched_regulatory_article} "
            f"(`{f.matched_regulatory_clause_id}`)"
            if f.matched_regulatory_clause_id
            else "_no matching regulation retrieved_"
        )
        parts.append(
            f"\n### {i}. {f.contract_clause_id} — risk **{f.risk}** "
            f"({f.verdict}, confidence {f.confidence:.2f})\n"
            f"**Cited regulation:** {cite}\n\n"
            f"{f.justification}\n"
        )
    return "\n".join(parts)


def _counts(findings: list[FindingOut]) -> dict[str, int]:
    out = {"High": 0, "Medium": 0, "Low": 0}
    for f in findings:
        out[f.risk] = out.get(f.risk, 0) + 1
    return out


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------


async def run_audit(
    audit_id: str,
    contract_id: str,
    clauses: list[ClauseInput],
) -> AuditState:
    """Execute the audit graph.

    Uses real LangGraph when available; otherwise falls back to a plain
    sequential `await` of the three node functions. Either way the contract
    is identical and observable via `state.trace`.
    """
    state = AuditState(audit_id=audit_id, contract_id=contract_id, clauses=clauses)
    try:
        from langgraph.graph import END, StateGraph

        builder = StateGraph(AuditState)
        builder.add_node("planner", planner_node)
        builder.add_node("tool_exec", tool_exec_node)
        builder.add_node("synthesiser", synthesiser_node)
        builder.set_entry_point("planner")
        builder.add_edge("planner", "tool_exec")
        builder.add_edge("tool_exec", "synthesiser")
        builder.add_edge("synthesiser", END)
        graph = builder.compile()
        # LangGraph's invoke returns the final state as a dict-like object.
        result = await graph.ainvoke(state)
        if isinstance(result, AuditState):
            return result
        if isinstance(result, dict):
            return AuditState(**result)
        return state
    except Exception as exc:
        # Plain sequential fallback - identical semantics, no LangGraph deps.
        state.add_trace("graph", f"LangGraph unavailable ({exc!r}); using sequential fallback.")
        await planner_node(state)
        await tool_exec_node(state)
        await synthesiser_node(state)
        return state


def run_audit_sync(audit_id: str, contract_id: str, clauses: list[ClauseInput]) -> AuditState:
    return asyncio.run(run_audit(audit_id, contract_id, clauses))
