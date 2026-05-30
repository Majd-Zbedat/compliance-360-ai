# Contract Datasets (3 Categories)

Your three Excel portfolios are the demo contract dataset:

| Category | Raw file | Contracts | Regulations checked |
|----------|----------|-----------|---------------------|
| **bank** | `raw/bank_contracts.xlsx` | 150 | SOX, PCI DSS, AML/KYC, Basel III, GDPR, ISO 27001, Local Law |
| **cybersecurity** | `raw/cybersecurity_contracts.xlsx` | 150 | NIST CSF, SOC 2, ISO 27001, GDPR, Privacy Controls, HIPAA |
| **ai** | `raw/ai_contracts.xlsx` | 150 | ISO 42001, GDPR, Privacy Controls, SOC 2, ISO 27001 |

Category → regulation mapping lives in `category_regulations.json`.

## Import / normalize

From project root:

```powershell
.\venv\Scripts\Activate.ps1
python scripts\import_contract_datasets.py
```

Outputs:

- `normalized/contracts_all.jsonl` (450 rows)
- `normalized/contracts_bank.jsonl`
- `normalized/contracts_cybersecurity.jsonl`
- `normalized/contracts_ai.jsonl`
- `splits/train.jsonl`, `val.jsonl`, `test.jsonl`

## API (orchestrator)

- `GET /contracts/categories` — list categories with regulation packs
- `GET /contracts?category=bank` — browse dataset contracts
- `POST /audits` with `contract_category` + `dataset_contract_id` — audit a dataset row
- `POST /audits` with `contract_category` + `document_b64` — audit an uploaded PDF in that category context

## Dashboard

The **Content Ingestion** zone on the dashboard lets you:

1. Pick **Banking**, **Cybersecurity**, or **AI**
2. See the relevant regulations for that portfolio
3. Select a contract from the dataset **or** upload your own PDF
4. Run the audit against the mapped regulation pack
