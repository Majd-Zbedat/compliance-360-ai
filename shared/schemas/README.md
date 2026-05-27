# auditor-schemas

Pydantic models shared across every backend service. Install in editable
mode from the project root:

```powershell
pip install -e ./shared/schemas
```

After that, all services can `from auditor_schemas import Audit, Finding, ...`.
