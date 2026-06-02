# AI-Native Regulatory Document Auditor

Compliance 360 control tower for legal teams. Upload a contract, run a full AI audit loop, and get risk-scored findings with regulatory citations (GDPR / ISO 27001 / Local Law), guarded by output safety rails.

---

## 1) What This Project Is

This project follows the reference layered architecture (UI -> Orchestrator -> Microservices -> LLM/Stores) and adapts the business logic from property triage to **regulatory contract auditing**.

Core workflow (Compliance 360 loop):

1. **Ingestion & Perception**: extract contract text + clauses
2. **RAG Retrieval**: fetch relevant regulatory clauses from ChromaDB
3. **Reasoning & Analysis**: classify findings and assign risk (High/Medium/Low)
4. **Guarded Output**: prevent unqualified legal-advice style output

---

## 2) What Was Built (Component by Component)

### Layer 1 - Frontend (`webui/`)

- Next.js 14 dashboard (enterprise-style layout)
- Pages:
  - `/` dashboard with KPI cards
  - `/audits` audit list
  - `/audits/new` upload / paste contract form
  - `/audits/[id]` detailed findings + drawer per finding
  - `/regulations` regulatory corpus browser
- Right-side assistant sheet scaffold (Ollama-ready)

### Layer 2 - Orchestrator (`services/orchestrator/`)

- FastAPI service acting as n8n stand-in for local development
- Executes the full pipeline end-to-end (`POST /audits`)
- Persists audit history in SQLAlchemy (SQLite by default, Postgres-ready)
- Provides APIs for dashboard data:
  - `/audits`, `/audits/{id}`, `/audits/stats`, `/regulations`

### Layer 3 - Microservices (`services/*`)

1. **RAG Service** (`rag_service`)
   - ChromaDB-backed retrieval (`POST /query`)
   - Seed ingestion endpoint (`POST /upsert`)
   - Citation-aware match return
2. **Doc Analyzer** (`doc_analyzer_service`)
   - PDF/base64 parsing with `pdfplumber`
   - Heuristic clause segmentation (`Article`, `Section`, numbered headings)
   - Clause type tagging (`liability`, `termination`, `data_processing`, etc.)
3. **Guardrails Service** (`guardrails_service`)
   - `POST /check/input`: reject off-topic/invalid submissions
   - `POST /check/output`: rewrite unsafe legal-advice phrasing
   - Optional LLM critic + Colang skeleton included
4. **LangGraph Agent Service** (`langgraph_agent_service`)
   - State transitions: `Drafting -> Reviewing -> Flagging -> Done`
   - Planner -> tool execution (`rag_search`) -> synthesiser
   - Per-clause verdict + risk assignment

### Layer 4 - LLM / Storage

- External LLM support (OpenAI / Gemini via env vars)
- Local Ollama intended for sidebar assistant
- ChromaDB for vector retrieval

---

## 3) Repository Structure

```text
FinalProject/
  webui/
  services/
    orchestrator/
    rag_service/
    doc_analyzer_service/
    guardrails_service/
    langgraph_agent_service/
  shared/
    schemas/
    prompts/
  scripts/
    seed_regulatory_corpus.py
    smoke_test.py
    run_dev.ps1
  data/
    regulatory_corpus/
    sample_contracts/
  docs/
    architecture.md
    prompt_engineering_log.md
  n8n/
    compliance_audit.json
```

---

## 4) The 12 Implementation Steps (Clear Breakdown)

These are the exact 12 steps completed from the core build plan.

### Step 1 - Bootstrap

Created base structure, `.gitignore`, `.env.example`, service folders, root/dependency files, and baseline project metadata.

### Step 2 - Shared Schemas

Created installable `auditor-schemas` package under `shared/schemas/` with canonical Pydantic models for contracts, regulations, findings, audits, and guardrail results.

### Step 3 - RAG Service

Implemented FastAPI RAG microservice with:

- ChromaDB persistent collections
- `/query` top-k retrieval with citation metadata
- `/upsert` data ingestion endpoint
- unit test for upsert + retrieval behavior

### Step 4 - Seed Corpus

Added corpus JSON files (GDPR, ISO27001, LocalLaw) and `scripts/seed_regulatory_corpus.py` to populate ChromaDB locally or through service endpoint.

### Step 5 - Doc Analyzer Service

Implemented PDF/text parsing and clause segmentation service:

- base64 document input
- page-aware extraction
- heading detection + clause type classification
- tests for segmentation/classification

### Step 6 - Guardrails Service

Implemented dual guardrail endpoints:

- Input validation rails (`/check/input`)
- Output rewrite rails (`/check/output`)
- optional OpenAI critic path
- Colang + YAML skeleton configs for NeMo-style rails

### Step 7 - LangGraph Agent Service

Implemented stateful reasoning microservice:

- `planner -> tool_exec -> synthesiser`
- clause-wise retrieval + risk verdict generation
- deterministic fallback when LLM unavailable
- tests for risk logic

### Step 8 - Orchestrator Service

Implemented central FastAPI pipeline:

- run full flow via `/audits`
- persist audits/findings
- expose list/detail/stats endpoints
- expose regulation browsing endpoint

### Step 9 - WebUI Bootstrap

Scaffolded Next.js app + Tailwind + reusable UI primitives, app shell with sidebar and assistant drawer, typed API client with env-configurable backend URL.

### Step 10 - WebUI Pages

Implemented all core pages and UX:

- dashboard KPIs + recent audits
- new audit submit flow
- audit detail with finding drill-down drawer
- regulation corpus exploration

### Step 11 - End-to-End Wiring + Smoke Validation

Added:

- sample contract (`data/sample_contracts/sample_msa.txt`)
- `scripts/smoke_test.py` for acceptance checks
- `scripts/run_dev.ps1` for launching all backend services
- confirmed end-to-end behavior including mixed risk levels + citations

### Step 12 - Docs + Prompt Baselines

Added architecture and prompt-engineering documentation:

- `docs/architecture.md`
- `docs/prompt_engineering_log.md`
- baseline prompts in `shared/prompts/*_v1.md`

---

## 5) How to Run (Step by Step)

## Prerequisites

- Python 3.10+
- Node.js 18+
- Existing virtual environment at `venv/` (already created)

## A. Backend Setup

```powershell
# from project root
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .\shared\schemas
Copy-Item .env.example .env
```

Optional: set `OPENAI_API_KEY` in `.env` to enable LLM critic/reasoning paths.

## B. Seed Regulatory Corpus

```powershell
python scripts\seed_regulatory_corpus.py
```

## C. Start Backend Services

### Option 1 — Docker (Layer 3 microservices, ports 8001–8004)

Stop `run_dev.ps1` first if those ports are already in use.

```powershell
.\scripts\docker_layer3.ps1
```

Manual equivalent:

```powershell
docker compose -f infra/docker-compose.yml up --build -d
python scripts\seed_regulatory_corpus.py --remote http://localhost:8001 --reset
```

Stop containers: `.\scripts\docker_layer3.ps1 -Down`

The orchestrator (port 8000) and dashboard still run on the host unless you add them to compose later.

### Option 2 — Local Python (all services including orchestrator)

```powershell
.\scripts\run_dev.ps1
```

### Option 3 — Manual (5 terminals)

```powershell
uvicorn services.rag_service.app.main:app --port 8001 --reload
uvicorn services.doc_analyzer_service.app.main:app --port 8002 --reload
uvicorn services.guardrails_service.app.main:app --port 8003 --reload
uvicorn services.langgraph_agent_service.app.main:app --port 8004 --reload
uvicorn services.orchestrator.app.main:app --port 8000 --reload
```

## D. Start Frontend

```powershell
cd webui
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## 6) How to Use the App

1. Go to `/audits/new`
2. Upload a contract PDF (or paste contract text)
3. Submit to run Compliance 360
4. Open generated audit detail page
5. Review:
   - risk labels
   - clause-level justifications
   - cited regulatory references
   - guardrail-safe final report

---

## 7) Validation / Test Commands

## Unit tests

```powershell
python -m pytest services -v
```

## End-to-end smoke test

```powershell
python scripts\smoke_test.py
```

Expected smoke-test outcome:

- Input accepted by guardrails
- Pipeline completes
- At least one `High`, one `Medium`, one `Low`
- Findings include real regulatory citations

---

## 8) Important Notes

- The RAG service includes a **hashing embedder fallback** if `sentence-transformers` is not present.
- Default persistence is SQLite (`data/auditor.db`), but DB URL is already configurable for Postgres.
- `n8n/compliance_audit.json` is included as a flow skeleton for parity with the reference architecture.

---

## 9) Main Files to Review

- `services/orchestrator/app/pipeline.py`
- `services/langgraph_agent_service/app/graph.py`
- `services/guardrails_service/app/rails.py`
- `services/rag_service/app/main.py`
- `services/doc_analyzer_service/app/segmenter.py`
- `webui/src/app/audits/[id]/page.tsx`
- `docs/architecture.md`
- `docs/prompt_engineering_log.md`

---

## 10) Next Suggested Improvements

1. Replace doc-analyzer heuristic with LayoutLMv3/fine-tuned classifier.
2. Swap orchestrator stand-in with real n8n execution in deployment.
3. Add true Ollama chat backend wiring in assistant drawer.
4. Add auth + tenant separation for multi-company compliance teams.


---

## 11) Your 3 Contract Categories Dataset

You provided and I integrated these files into the project:

- `data/contract_datasets/raw/bank_contracts.xlsx`
- `data/contract_datasets/raw/cybersecurity_contracts.xlsx`
- `data/contract_datasets/raw/ai_contracts.xlsx`

To normalize them into JSONL for ingestion/training:

```powershell
.\venv\Scripts\Activate.ps1
python scripts\import_contract_datasets.py
```

Generated outputs:

- `data/contract_datasets/normalized/contracts_all.jsonl`
- `data/contract_datasets/normalized/contracts_bank.jsonl`
- `data/contract_datasets/normalized/contracts_cybersecurity.jsonl`
- `data/contract_datasets/normalized/contracts_ai.jsonl`
- `data/contract_datasets/splits/train.jsonl`
- `data/contract_datasets/splits/val.jsonl`
- `data/contract_datasets/splits/test.jsonl`

See `data/contract_datasets/README.md` for details.
