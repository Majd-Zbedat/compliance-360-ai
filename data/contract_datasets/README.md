# Contract Datasets (3 Categories)

Your three Excel portfolios are the demo contract dataset:

| Category | Raw file | Contracts | Regulations checked |
|----------|----------|-----------|---------------------|
| **bank** | `raw/bank_contracts.xlsx` | 150 | SOX, PCI DSS, AML/KYC, Basel III, GDPR, ISO 27001, Local Law |
| **cybersecurity** | `raw/cybersecurity_contracts.xlsx` | 150 | NIST CSF, SOC 2, ISO 27001, GDPR, Privacy Controls, HIPAA |
| **ai** | `raw/ai_contracts.xlsx` | 150 | ISO 42001, GDPR, Privacy Controls, SOC 2, ISO 27001 |

Category → regulation mapping lives in `category_regulations.json`.

## Import / normalize

Copy your Excel files into `raw/`:

- `bank_contracts.xlsx`
- `cybersecurity_contracts.xlsx`
- `ai_contracts.xlsx`

From project root:

```powershell
.\venv\Scripts\Activate.ps1
python scripts\import_contract_datasets.py
python scripts\seed_contract_corpus.py --remote http://54.87.42.101:8001
```

The second command indexes all 450 portfolio rows into RAG so the Compliance AI Assistant can answer dataset questions via vector search.

Also writes `portfolio_summaries.json` (KPI rows from summary sheets + aggregates).

Outputs:

- `normalized/contracts_all.jsonl` (450 rows)
- `normalized/contracts_bank.jsonl`
- `normalized/contracts_cybersecurity.jsonl`
- `normalized/contracts_ai.jsonl`
- `splits/train.jsonl`, `val.jsonl`, `test.jsonl`

## API (orchestrator)

- `GET /contracts/categories` — list categories with regulation packs
- `GET /contracts?category=bank` — browse dataset contracts
- `GET /contracts/portfolio-stats?category=bank` — portfolio KPIs for the Compliance AI Assistant
- `POST /chat` with `contract_category` — portfolio-aware Q&A
- `POST /chat` with `audit_id` — Q&A about a contract you already audited (select in dashboard chat header)
- `POST /contracts/sync-rag` — index all 450 portfolio rows into RAG (run once after import)
- `POST /audits/sync-rag` — re-index past uploaded audits into RAG for chat
- `POST /audits` with `contract_category` + `dataset_contract_id` — audit a dataset row
- `POST /audits` with `contract_category` + `document_b64` — audit an uploaded PDF (auto-indexed to RAG after audit)

## Dashboard

The **Content Ingestion** zone on the dashboard lets you:

1. Pick **Banking**, **Cybersecurity**, or **AI**
2. See the relevant regulations for that portfolio
3. Select a contract from the dataset **or** upload your own PDF
4. Run the audit against the mapped regulation pack
