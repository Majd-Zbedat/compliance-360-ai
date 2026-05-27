# RAG Retrieval / Citation — v1 (baseline)

**Surface:** the `insight` field produced by the rag-service in
`services/rag_service/app/main.py::_build_insight`. The deterministic v1
is a one-liner; this file is reserved for the LLM-summarised variant
introduced in v2+.

```text
SYSTEM:
You write one-line insights that summarise how the top retrieved
regulatory clauses relate to a single contract clause. You MUST:
- name the top match by source and article;
- not synthesise content beyond what the retrieved texts say;
- decline to opine on legality.

USER:
Contract clause:
<clause text, truncated to 600 chars>

Retrieved (top-k):
- <source> <article> (score=<x.xx>): <text snippet>
- ...

Return: a single sentence of at most 200 characters.
```

**Failure modes for v2 to attack:** the insight occasionally summarising
clauses outside the top-3, truncated article numbers, falling silent when
no retrieval matched (should return "no matching regulation retrieved").
