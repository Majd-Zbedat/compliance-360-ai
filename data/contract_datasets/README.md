# Contract Datasets (3 Categories)

Raw files copied into this project:

- `raw/bank_contracts.xlsx`
- `raw/cybersecurity_contracts.xlsx`
- `raw/ai_contracts.xlsx`

## Normalize to JSONL

From project root:

```powershell
.\venv\Scripts\Activate.ps1
python scripts\import_contract_datasets.py
```

Optional tuning:

```powershell
python scripts\import_contract_datasets.py --min-chars 120 --seed 7 --train 0.8 --val 0.1
```

## Outputs

- `normalized/contracts_all.jsonl`
- `normalized/contracts_bank.jsonl`
- `normalized/contracts_cybersecurity.jsonl`
- `normalized/contracts_ai.jsonl`
- `splits/train.jsonl`
- `splits/val.jsonl`
- `splits/test.jsonl`

## Normalized record format

```json
{
  "id": "bank_Sheet1_42",
  "category": "bank",
  "source_file": "bank_contracts.xlsx",
  "sheet_name": "Sheet1",
  "text": "...contract text...",
  "title": "...optional...",
  "external_id": "...optional...",
  "metadata": {
    "raw": { "...all original columns...": "..." },
    "text_column": "...",
    "id_column": "...",
    "title_column": "..."
  }
}
```

This format keeps all original fields for traceability while providing a clean
`text` field for ingestion, chunking, and model training.
