"""Guardrails service - Layer 3.3.

Dual endpoint, mirroring the reference PDF:

  POST /check/input   - validates user-submitted contract text
  POST /check/output  - validates AI-generated audit report, rewriting
                        unqualified legal advice into safe analysis.

Implementation is rule-based (pure Python) with an optional LLM critic
when `OPENAI_API_KEY` is set. A Colang skeleton lives in
`services/guardrails_service/rails/auditor.co` for parity with the
reference architecture's NeMo Guardrails setup.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .rails import check_input, check_output, llm_critic
from .schemas import GuardrailCheckRequest, GuardrailCheckResponse

app = FastAPI(
    title="Compliance Guardrails Service",
    description="Input + output guardrails for the regulatory audit pipeline.",
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
        "llm_critic_enabled": bool(settings.openai_api_key and settings.enable_llm_critic),
    }


@app.post("/check/input", response_model=GuardrailCheckResponse)
def check_input_endpoint(req: GuardrailCheckRequest) -> GuardrailCheckResponse:
    return GuardrailCheckResponse(**check_input(req.text))


@app.post("/check/output", response_model=GuardrailCheckResponse)
def check_output_endpoint(req: GuardrailCheckRequest) -> GuardrailCheckResponse:
    result = check_output(req.text)
    critic = llm_critic(result.get("safe_text") or req.text)
    if critic is not None:
        merged_rules = sorted(set(result.get("matched_rules", []) + critic.get("matched_rules", [])))
        if not critic["passed"]:
            return GuardrailCheckResponse(
                passed=False,
                reason=critic.get("reason"),
                safe_text=critic.get("safe_text"),
                matched_rules=merged_rules,
            )
        return GuardrailCheckResponse(
            passed=True,
            reason=result.get("reason"),
            safe_text=critic.get("safe_text") or result.get("safe_text"),
            matched_rules=merged_rules,
        )
    return GuardrailCheckResponse(**result)
