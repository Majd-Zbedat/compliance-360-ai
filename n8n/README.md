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
5. **Node 5 — AI Agent** — calls tools `rag_query`, `langgraph_agent`, `doc_analyse` (reference architecture)
6. Normalize agent JSON into dashboard report shape (Node 6 / 6c)
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
| `langgraph_agent_service` | 8004 | **`langgraph_agent` tool** on Node 5 AI Agent |

Start all services from the project root:

```powershell
.\scripts\run_dev.ps1
```

### Docker n8n → host services

The exported JSON uses **literal** URLs (no `$env`) because many local n8n installs block env access in nodes.

**Local Layer 3** (all services on the laptop):

```text
http://host.docker.internal:8003/check/input
http://host.docker.internal:8004/agent/run
```

**EC2 Layer 3** (microservices on AWS; n8n still on laptop Docker):

The repo export uses your EC2 public IP, e.g.:

```text
http://44.223.109.220:8003/check/input
http://44.223.109.220:8004/agent/run
```

After changing `n8n/compliance_audit.json`, **re-import** the workflow in n8n:

1. n8n UI → **Workflows** → **Import from File** → select `n8n/compliance_audit.json` (overwrite or delete the old workflow first).
2. Open the workflow → **Activate**.
3. Re-attach **Google Gemini** credentials on Node 4 and Node 5.
4. Confirm tool/HTTP nodes show `44.223.109.220` (or your Elastic IP), not `host.docker.internal`.

If n8n runs **natively on Windows** (not Docker), use `http://127.0.0.1:<port>` for local Layer 3 only.

See `infra/EC2_DEPLOY.md` for full EC2 + laptop wiring.

After import, re-attach your **Google Gemini** credentials on:

- Gemini Chat Model — Extractor (Node 4)
- Gemini Chat Model — Agent (Node 5)

---

## 2b) Main path (Option A — reference architecture)

```text
Node 1 → Node 2 → Node 3 → Node 4 → Node 4b → Node 5 (AI Agent) → Node 6 → Node 6c → Node 7 → …
```

**Tools (dashed lines into Node 5):**

| Tool | Service | Purpose |
|------|---------|---------|
| `rag_query` | 8001 `/query` | Agent calls RAG first; `$fromAI('clause_text')` |
| `langgraph_agent` | 8004 `/agent/run` | Pre-built payload (no 422); agent invokes once |
| `doc_analyse` | 8002 `/analyse` | Optional PDF segmentation |

Legacy nodes **Build LangGraph Payload**, **Run LangGraph Audit**, **RAG Regulatory Query** (HTTP) remain in the JSON export but are **not** on the main path.

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

### Node 5 — AI Agent (main audit orchestrator)
- **Type:** `agent` (Tools Agent)
- **Model:** Gemini Chat Model — Agent
- **Tools:** `rag_query`, `langgraph_agent`, `doc_analyse` (dashed `ai_tool` connections)
- **Flow:** Agent calls `rag_query` first, then `langgraph_agent` once, then returns structured JSON
- **langgraph_agent body:** Pre-built expression from webhook + Node 4b (avoids HTTP 422)

### rag_query (tool)
- **Type:** `toolHttpRequest`
- **Calls:** `POST http://host.docker.internal:8001/query`
- **Body:** `{ text: $fromAI('clause_text'), top_k: 5 }`
- **Purpose:** Retrieve similar regulations before LangGraph runs.

### doc_analyse (tool)
- **Type:** `toolHttpRequest`
- **Calls:** `POST http://host.docker.internal:8002/analyse`
- **Purpose:** Optional PDF segmentation when webhook includes `document_b64`.

### langgraph_agent (tool)
- **Type:** `toolHttpRequest`
- **Calls:** `POST http://host.docker.internal:8004/agent/run`
- **Body:** Pre-built from `$execution.id`, webhook description, Node 4b metadata (no `$fromAI` for clauses)
- **Purpose:** Deterministic LangGraph audit; invoke once per execution.

### Run LangGraph Audit (legacy — not on main path)
- **Type:** `httpRequest`
- **Status:** Bypassed when using Option A. Kept in export for fallback experiments.

### RAG Regulatory Query (legacy HTTP — not on main path)
- **Status:** Replaced by **`rag_query` tool** on Node 5.

### Node 6 — Final Report LLM Chain
- **Type:** `code`
- **Purpose:** Parse Node 5 agent output into the dashboard report schema (`findings`, `routing_decision`, `overall_risk`, etc.).
- **Input:** `$('Node 5 — AI Agent').item.json`

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
Node 3 (true)  -> Node 4 -> Node 4b -> Node 5 -> Node 6 -> Node 6c -> Node 7 -> Node 7b
Node 3 (false) -> Node 3b
Node 7b (true) -> Node 8
Node 7b (false)-> Node 7d
Node 8 output0 -> Node 8a
Node 8 output1 -> Node 8b
Node 8 fallback-> Node 8c
```

Tool edges (dashed into Node 5):

```text
rag_query        -> Node 5 (ai_tool)
langgraph_agent  -> Node 5 (ai_tool)
doc_analyse      -> Node 5 (ai_tool)
Gemini Agent model -> Node 5 (ai_languageModel)
Gemini Extractor model -> Node 4 (ai_languageModel)
```

---

## 6) How to Connect Nodes in n8n UI (Manual Build Order)

If you build manually instead of import:

1. Add Nodes 1, 2, 3, 3b and connect linear + reject branch.
2. Add Node 4 + Gemini Extractor model; connect model to Node 4.
3. Add Node 4b and connect Node 4 -> Node 4b.
4. Add **Node 5 AI Agent** + Gemini Agent model; connect Node 4b -> Node 5 -> Node 6.
5. Add tool nodes `rag_query`, `langgraph_agent`, `doc_analyse`; connect each to Node 5 **Tool** port (dashed).
6. Configure `langgraph_agent` jsonBody with pre-built payload (see `compliance_audit.json`).
7. Add Node 6 (Code) + Node 6c; Node 6 reads `$('Node 5 — AI Agent').item.json`.
8. Add Nodes 7 and 7b; connect Node 6c -> 7 -> 7b.
9. Add Node 7d and connect Node 7b false -> Node 7d.
10. Add Node 8 and connect Node 7b true -> Node 8.
11. Add Nodes 8a/8b/8c and connect outputs 0/1/fallback from Node 8.

---

## 7) Local Test Command

```powershell
$body = @{
  description = "Master Services Agreement between Acme and Beta. EU data processing, no DPA, broad liability limits."
  filename    = "msa_acme_beta.txt"
  requester   = "Sarah Chen"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:9090/webhook/compliance-audit" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

---

## 8) Common Pitfalls

1. **Gemini credentials not set after import** -> Node 4 or Node 5 fail immediately.
2. **Wrong service hostnames in Docker** -> use `host.docker.internal` (already in JSON).
3. **`description` too short** -> guardrails input may fail; use full contract paragraphs for demos.
4. **LangGraph HTTP 422** -> do not let the agent build `clauses` via `$fromAI`; use pre-built `langgraph_agent` jsonBody in the tool node.
5. **RAG as main-path HTTP** -> wrong for Option A; wire `rag_query` to Node 5 Tool port instead.
6. **Human review webhook unavailable** -> flow still returns Node 7d response (designed fallback).
7. **Legacy Run LangGraph path** -> if re-enabling bypass HTTP nodes, use **Build LangGraph Payload** + `={{ $json }}` body to avoid newline JSON errors.

---

## 9) Suggested Next Improvements

1. Wire `doc_analyse` for PDF uploads when webhook sends `document_b64`.
2. Multi-clause PDFs: expand `langgraph_agent` payload to pass all clauses from doc-analyzer.
3. Orchestrator already posts to this webhook via `N8N_WEBHOOK_URL` (port **9090**),
   persists results to SQLite. Verify: `curl http://localhost:8000/healthz` → `"pipeline_driver": "n8n"`.
   To fall back to the Python pipeline, set `N8N_WEBHOOK_URL=` (empty) in `.env`.
4. Send Node 7b false path to Node 7c first, then Node 7d, if you require guaranteed human-review notification.
5. Add webhook auth/signature for production.

---

## 10) End-to-End Test: Layer 1 (UI) ↔ Layer 2 (n8n)

Goal: confirm a contract uploaded in the dashboard flows through the orchestrator
→ n8n → microservices and back into the UI.

1. **Start backend services** (RAG 8001, doc-analyzer 8002, guardrails 8003,
   langgraph 8004, orchestrator 8000):

   ```powershell
   .\scripts\run_dev.ps1
   ```

2. **Start n8n** (Docker) and **Activate** the `compliance_audit` workflow so the
   production webhook `/webhook/compliance-audit` is live.

3. **Point the orchestrator at n8n** — in the repo `.env`:

   ```text
   N8N_WEBHOOK_URL=http://localhost:9090/webhook/compliance-audit
   ```

   Confirm: `curl http://localhost:8000/healthz` → `"pipeline_driver": "n8n"`.

4. **Start the UI** and upload a contract on the Dashboard:

   ```powershell
   cd webui ; npm run dev
   ```

   - Drop a contract **PDF** (or `.txt`) on the dashboard Content Ingestion zone.
   - Optionally expand **Optional details** (jurisdiction / contract type) to aid analysis.
   - Click **Analyze contract** → you land on `/audits/{id}` with risk, findings,
     cited regulations, and a **Recommended correction** per finding.

5. **Scanned PDFs:** if the PDF is image-only and the OCR stack isn't installed,
   the audit still completes and the result notes that little text was extracted —
   paste the text instead, or install the optional OCR stack (see
   `services/doc_analyzer_service/requirements.txt`).

### Upload new regulations (PDF or text)

`POST http://localhost:8000/regulations` indexes a new source into the RAG store
and appends it to the local corpus so it appears in the **Regulation Library** and
re-seeds. The UI exposes this via **Regulations → Add Regulation** (paste text or
upload a PDF/TXT).

```powershell
$body = @{ source = "Custom Vendor Policy"; article = "Sec. 1"; text = "Vendors must encrypt cardholder data at rest and in transit and notify within 72 hours of a breach." } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/regulations" -Method POST -ContentType "application/json" -Body $body
```

