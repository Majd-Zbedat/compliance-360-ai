# Compliance 360 n8n Flow Guide

This document explains the workflow in `n8n/compliance_audit.json` step by step:

- what each node does
- how nodes are connected
- what input/output shape to expect
- how to run and test locally

---

## 1) Flow Overview

The workflow is a guarded contract-audit pipeline:

1. Receive a submission from WebUI via webhook
2. Run input guardrails
3. If rejected, return 422 immediately
4. If accepted, extract metadata with LLM (Node 4 / 4b)
5. **Run LangGraph Audit** — deterministic HTTP POST to `/agent/run` (bypasses Node 5)
6. Normalize LangGraph JSON into dashboard report shape (Node 6 / 6c)
7. Run output guardrails
8. If output flagged, return `human_review_required`
9. If output passes, route to escalation/reviewer_queue/auto_file

---

## 2) Required Services

The n8n flow expects these services running on the host:

| Service | Port | Used by |
|---------|------|---------|
| `rag_service` | 8001 | LangGraph internally (+ optional `rag_query` tool) |
| `doc_analyzer_service` | 8002 | Optional `doc_analyse` tool (PDF path) |
| `guardrails_service` | 8003 | Nodes 2 and 7 |
| `langgraph_agent_service` | 8004 | **Run LangGraph Audit** |

Start all services from the project root:

```powershell
.\scripts\run_dev.ps1
```

### Docker n8n → host services

The exported JSON uses **literal** URLs (no `$env`) because many local n8n installs block env access in nodes:

```text
http://host.docker.internal:8003/check/input
http://host.docker.internal:8004/agent/run
```

If n8n runs **natively on Windows** (not Docker), change these to `http://127.0.0.1:<port>`.

After import, re-attach your **Google Gemini** credentials on:

- Gemini Chat Model — Extractor (Node 4)
- Google Gemini Chat Model (Node 6 report chain)

---

## 3) Expected Webhook Input

`Node 1 — Webhook Trigger` listens on:

- test URL: `/webhook-test/compliance-audit`
- production URL: `/webhook/compliance-audit`

Expected body:

```json
{
  "description": "Contract text goes here...",
  "filename": "msa_acme_beta.txt",
  "requester": "Sarah Chen"
}
```

`description` is required for flow usefulness.

---

## 4) Node-by-Node Explanation

### Node 1 — Webhook Trigger
- **Type:** `webhook`
- **Purpose:** Entry point from UI/backend.
- **Output:** Original request body under `$json.body`.

### Run LangGraph Audit
- **Type:** `httpRequest`
- **Calls:** `POST http://host.docker.internal:8004/agent/run`
- **Purpose:** Main audit engine — builds a fixed JSON body from webhook `description` and Node 4b metadata (no LLM tool calls, avoids 422 validation errors).
- **Body:** `audit_id`, `contract_id`, single `clauses[]` entry, `jurisdiction`, `contract_type`.
- **Output:** LangGraph response with `findings`, `overall_risk`, `report_markdown`, `trace`.

### Node 2 — Guardrails Input Check
- **Type:** `httpRequest`
- **Calls:** `POST http://host.docker.internal:8003/check/input`
- **Body:** `{ "text": $json.body.description }`
- **Purpose:** Early reject unsafe/off-topic submissions.
- **Output fields used later:** `passed`, `reason`.

### Node 3 — Pass / Reject Router
- **Type:** `if`
- **Condition:** `$json.passed == true`
- **True path:** continue to extraction (Node 4)
- **False path:** reject response (Node 3b)

### Node 3b — Reject Response
- **Type:** `respondToWebhook`
- **Returns:** HTTP 422 with `{ success: false, rejected: true, reason }`
- **Purpose:** Immediate fail-fast response when input guardrails fail.

### Gemini Chat Model — Extractor
- **Type:** Gemini model node
- **Purpose:** Language model backend for Node 4 chain.
- **Connection:** `ai_languageModel` -> Node 4.

### Node 4 — Extract contract (LLM)
- **Type:** `chainLlm`
- **Purpose:** Extract structured contract metadata from free text.
- **Prompt output target fields:**
  - `contract_type`
  - `parties`
  - `jurisdiction`
  - `sensitive_topics`
  - `key_concerns`
  - `routing_decision`

### Node 4b — Parse extracted JSON
- **Type:** `code`
- **Purpose:** Robust JSON parsing + normalization.
- **Behavior:**
  - strips markdown fences
  - parses JSON safely
  - defaults invalid `routing_decision` to `reviewer_queue`
- **Output:** normalized metadata under `output`.

### Gemini Chat Model — Agent
- **Type:** Gemini model node
- **Purpose:** LLM backend for Node 5 agent.
- **Connection:** `ai_languageModel` -> Node 5.

### Node 5 — AI Agent (optional / bypassed)
- **Type:** `langchain agent`
- **Status:** **Not on the main execution path.** Node 5 remains on the canvas for future multi-tool orchestration.
- **Why bypassed:** The `langgraph_agent` AI tool often sent malformed `clauses` payloads (HTTP 422). **Run LangGraph Audit** replaces it with a deterministic HTTP node.

### rag_query (tool)
- **Type:** `toolHttpRequest`
- **Calls:** `POST {RAG_URL}/query`
- **Status:** Present but **not connected** to Node 5.

### doc_analyse (tool)
- **Type:** `toolHttpRequest`
- **Calls:** `POST {DOC_ANALYZER_URL}/analyse`
- **Status:** Present but **not connected** to Node 5.

### langgraph_agent (tool)
- **Type:** `toolHttpRequest`
- **Calls:** `POST http://host.docker.internal:8004/agent/run`
- **Status:** Wired to Node 5 only; **not used** on the active path.

### Node 6 — Final Report LLM Chain
- **Type:** `chainLlm`
- **Purpose:** Map **Run LangGraph Audit** JSON into the dashboard report schema (`findings`, `routing_decision`, `overall_risk`, etc.).
- **Input expression:** `$('Run LangGraph Audit').item.json`
- **Model backend:** Google Gemini Chat Model node.

### Node 6b — Parse report JSON
- **Type:** `outputParserStructured`
- **Status:** helper node present for parity; main path currently uses Node 6c parser.

### Node 6c — Parse report JSON
- **Type:** `code`
- **Purpose:** Final hardening parser and defaults.
- **Behavior:**
  - parse JSON robustly
  - apply fallback object if invalid
  - infer `routing_decision` from `overall_risk` if missing

### Node 7 — Guardrails Output Check
- **Type:** `httpRequest`
- **Calls:** `POST {GUARDRAILS_URL}/check/output`
- **Body:** `{ "text": JSON.stringify($json) }`
- **Purpose:** Validate generated report before release.

### Node 7b — Output Pass / Flag Router
- **Type:** `if`
- **Condition:** `$json.passed == true`
- **True path:** route by decision (Node 8)
- **False path:** respond human review pending (Node 7d)

### Node 7c — Human Review Webhook
- **Type:** `httpRequest`
- **Purpose:** Optional side effect to notify external human-review system.
- **Current wiring:** It is connected to Node 7d, but Node 7b false path goes directly to Node 7d.

### Node 7d — Respond human review pending
- **Type:** `respondToWebhook`
- **Returns:** HTTP 200 with `human_review_required: true`.

### Node 8 — Routing Decision Router
- **Type:** `switch`
- **Switch key:** `routing_decision`
- **Rule outputs:**
  - `escalation` -> Node 8a
  - `reviewer_queue` -> Node 8b
  - fallback (`extra`) -> Node 8c

### Node 8a — Escalation Response
- **Type:** `respondToWebhook`
- **Returns:** `{ success: true, channel: "escalation", report }`

### Node 8b — Reviewer Queue Response
- **Type:** `respondToWebhook`
- **Returns:** `{ success: true, channel: "reviewer_queue", report }`

### Node 8c — Auto File Response
- **Type:** `respondToWebhook`
- **Returns:** `{ success: true, channel: "auto_file", report }`

### Google Gemini Chat Model
- **Type:** Gemini model node
- **Purpose:** Language model backend for Node 6 report normalization.

---

## 5) Connection Map (Exactly as in JSON)

Main graph:

```text
Node 1 -> Node 2 -> Node 3
Node 3 (true)  -> Node 4 -> Node 4b -> Run LangGraph Audit -> Node 6 -> Node 6c -> Node 7 -> Node 7b
Node 3 (false) -> Node 3b
Node 7b (true) -> Node 8
Node 7b (false)-> Node 7d
Node 8 output0 -> Node 8a
Node 8 output1 -> Node 8b
Node 8 fallback-> Node 8c
```

Model edges (active path):

```text
Gemini Extractor model -> Node 4
Google Gemini model    -> Node 6
```

Optional (not on main path): Node 5 + `langgraph_agent`, `rag_query`, `doc_analyse` tools.

---

## 6) How to Connect Nodes in n8n UI (Manual Build Order)

If you build manually instead of import:

1. Add Nodes 1, 2, 3, 3b and connect linear + reject branch.
2. Add Node 4 + Gemini Extractor model; connect model to Node 4.
3. Add Node 4b and connect Node 4 -> Node 4b.
4. Add **Run LangGraph Audit** HTTP node; connect Node 4b -> Run LangGraph Audit -> Node 6.
5. Add Node 6 + Gemini model + Node 6c; point Node 6 prompt at `$('Run LangGraph Audit').item.json`.
6. Add Nodes 7 and 7b; connect Node 6c -> 7 -> 7b.
7. Add Node 7d and connect Node 7b false -> Node 7d.
8. Add Node 8 and connect Node 7b true -> Node 8.
9. Add Nodes 8a/8b/8c and connect outputs 0/1/fallback from Node 8.
10. (Optional) Add Node 7c and wire as needed for external review side effects.

---

## 7) Local Test Command

```powershell
$body = @{
  description = "Master Services Agreement between Acme and Beta. EU data processing, no DPA, broad liability limits."
  filename    = "msa_acme_beta.txt"
  requester   = "Sarah Chen"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:5678/webhook/compliance-audit" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

---

## 8) Common Pitfalls

1. **Gemini credentials not set after import** -> Node 4 or Node 6 fail immediately.
2. **Wrong service hostnames in Docker** -> use `host.docker.internal` (already in JSON).
3. **`description` too short** -> guardrails input may fail; use full contract paragraphs for demos.
4. **Re-enabling Node 5 `langgraph_agent` tool** -> likely HTTP 422 unless tool body uses `$fromAI(..., 'json')` for `clauses`.
5. **`doc_analyse` / `rag_query`** -> present as tools but not on main path; add HTTP nodes when wiring PDF upload.
6. **Human review webhook unavailable** -> flow still returns Node 7d response (designed fallback).

---

## 9) Suggested Next Improvements

1. Add HTTP `doc_analyse` before Run LangGraph when webhook accepts `document_b64` (PDF upload).
2. Add HTTP `rag_query` before Node 6 for extra `similar_regulations` in the report.
3. Wire orchestrator `POST /audits` to this webhook for frontend integration.

   The orchestrator (port **8000**) is configured via `N8N_WEBHOOK_URL` (default
   `http://localhost:5678/webhook/compliance-audit`). The Next.js UI posts to
   `POST /audits` unchanged; the orchestrator extracts PDF/text, calls n8n,
   and persists results to SQLite.

   Verify: `curl http://localhost:8000/healthz` → `"pipeline_driver": "n8n"`.

   To fall back to the Python pipeline, set `N8N_WEBHOOK_URL=` (empty) in `.env`.
4. Send Node 7b false path to Node 7c first, then Node 7d, if you require guaranteed human-review notification.
5. Add webhook auth/signature for production.

