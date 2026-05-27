"""LangGraph agent service - Layer 3.4.

POST /agent/run - run the planner -> tool_exec -> synthesiser state
machine over a list of pre-extracted contract clauses.

The agent's state transitions are observable via `trace` in the response,
and the audit status field advances Drafting -> Reviewing -> Flagging ->
Done as nodes execute.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .graph import run_audit
from .schemas import AgentRunRequest, AgentRunResponse

app = FastAPI(
    title="LangGraph Compliance Agent",
    description="Stateful audit reasoning over extracted contract clauses.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok",
        "service": settings.service_name,
        "rag_service_url": settings.rag_service_url,
        "llm_reasoning_enabled": bool(settings.openai_api_key and settings.enable_llm_reasoning),
    }


@app.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(req: AgentRunRequest) -> AgentRunResponse:
    if not req.clauses:
        raise HTTPException(status_code=400, detail="clauses must be non-empty")
    state = await run_audit(
        audit_id=req.audit_id,
        contract_id=req.contract_id,
        clauses=req.clauses,
    )
    return AgentRunResponse(
        audit_id=state.audit_id,
        contract_id=state.contract_id,
        status=state.status,
        overall_risk=state.overall_risk,
        findings=state.findings,
        report_markdown=state.report_markdown,
        trace=state.trace,
    )
