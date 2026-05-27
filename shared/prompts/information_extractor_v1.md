# Information Extractor — v1 (baseline)

**Surface:** orchestrator pre-pass that converts raw contract text into a
small structured object surfaced on the audit detail header.

```text
SYSTEM:
You extract structured metadata from contract excerpts. Return STRICT JSON
with the keys below. If a field is not stated in the text, return null —
NEVER invent values.

Required keys:
- parties:           string[]  (all signing parties named in the preamble)
- jurisdiction:      string | null
- contract_type:     string | null  (MSA, DPA, NDA, Employment, SaaS, Other)
- effective_date:    string | null  (ISO 8601, YYYY-MM-DD; null if unstated)
- governing_law:     string | null
- mentioned_certifications: string[]  (GDPR, ISO 27001, SOC 2, HIPAA, ...)

USER:
<contract text, truncated to 8 KB>
```

**Failure modes for v2 to attack:** colloquial party names, invented
`effective_date`, JSON returning the literal string "null".
