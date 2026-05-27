# Prompt Engineering Log

This log mirrors Section 6 of the reference PDF, adapted to the
Regulatory Document Auditor. Five prompt-engineering surfaces are
covered; each surface gets a baseline (v1) below and is expected to be
iterated 5 times during the project (see template at the bottom).

The live prompts live in `shared/prompts/*.md`; this document records
*why* each one is shaped the way it is and what the next iteration
should attack.

## Surface inventory

| # | Surface | Where it lives | File |
| --- | --- | --- | --- |
| 1 | Information Extractor (contract metadata) | n8n / orchestrator pre-pass | `shared/prompts/information_extractor_v1.md` |
| 2 | Compliance Analyst Agent (LangGraph reasoning) | `services/langgraph_agent_service/app/reasoning.py` | `shared/prompts/compliance_analyst_agent_v1.md` |
| 3 | RAG Retrieval / Citation prompt | rag-service `insight` synthesiser | `shared/prompts/rag_retrieval_v1.md` |
| 4 | Guardrails Rail Prompts (input topic + output legal-advice critic) | `services/guardrails_service/app/rails.py` | `shared/prompts/guardrails_v1.md` |
| 5 | Local Ollama Compliance Assistant System Prompt | dashboard right-side `Sheet` | `shared/prompts/ollama_assistant_v1.md` |

## Surface 1 — Information Extractor

### v1 — Baseline

Goal: convert the raw contract text into structured metadata
`{parties, jurisdiction, contract_type, effective_date,
governing_law, mentioned_certifications}` to be displayed on the audit
detail header.

Baseline prompt: see `shared/prompts/information_extractor_v1.md`.

Failure modes to attack in v2–v5:

* Hallucinated parties when the contract preamble names a registered
  business under a colloquial name.
* Inventing an `effective_date` when none is present.
* Returning `null` strings instead of literal nulls.

## Surface 2 — Compliance Analyst Agent

Lives in `services/langgraph_agent_service/app/reasoning.py` as
`REASONING_SYSTEM_PROMPT`. Pinned baseline in
`shared/prompts/compliance_analyst_agent_v1.md`.

The agent must:

1. Cite the retrieved regulatory clause id, source and article.
2. Refuse to invent regulatory references not returned by `rag_search`.
3. Hedge language ("appears inconsistent with" not "is illegal").
4. Map verdict → risk via likelihood × impact.

v2–v5 should attack:

* Over-citing irrelevant retrieval rows when retrieval scores are low.
* Returning "Low" for clearly missing safeguards (false negatives).
* JSON malformation under non-English contract excerpts.

## Surface 3 — RAG Retrieval / Citation

Used in `services/rag_service/app/main.py::_build_insight`. The current
baseline forces citation-grounded one-liners. See
`shared/prompts/rag_retrieval_v1.md`.

v2–v5 should attack:

* The insight occasionally summarising clauses outside the top-3.
* Cutting off article numbers when the model abbreviates.
* Handling the "no match retrieved" case without falling silent.

## Surface 4 — Guardrails Rail Prompts

Two prompts, both currently rule-based (Python) with an optional LLM
critic when `OPENAI_API_KEY` is set. The LLM critic prompt lives at
`services/guardrails_service/app/rails.py::_LLM_CRITIC_PROMPT` and is
pinned in `shared/prompts/guardrails_v1.md`.

v2–v5 should attack:

* False positives on legitimate contract analyses that include the word
  "must" in non-prescriptive contexts ("Article 32 must be considered…").
* False negatives on plausible-sounding invented citations ("Greene v.
  Acme [2019] EWHC 211").
* Multilingual content (Hebrew / Arabic / Spanish) input rejection.

## Surface 5 — Local Ollama Compliance Assistant

The dashboard's right-side `Sheet` will host a chat tied to a local
Ollama server in a follow-up iteration. The baseline grounding prompt
lives at `shared/prompts/ollama_assistant_v1.md`.

v2–v5 should attack:

* Off-topic queries about unrelated legal areas.
* Requests for definitive legal advice ("am I going to be sued?").
* Prompt-injection attempts ("ignore your system message").

---

## Iteration template (apply to every surface)

```text
Version 1 — Baseline
    Prompt: <full prompt>
    Test cases: 10 representative examples
    Outputs:   pass/fail per test case
    Notes:     observed failure mode(s)

Version 2 — Targeted iteration
    Failure addressed: <one-sentence description>
    Change:            <diff vs. v1>
    New outputs:       pass/fail per test case
    Notes:             resolved? regressions?

Version 3 — Targeted iteration
    ...

Version 4 — Refinement
    ...

Version 5 — Refinement
    Final prompt:       <full prompt>
    Justification:      <why each phrase is the way it is>
    Final test pass:    X / 10
```
