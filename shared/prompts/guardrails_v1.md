# Guardrails — v1 (baseline)

**Surface:** dual-endpoint rails. The Python implementation in
`services/guardrails_service/app/rails.py` performs deterministic
detection + rewrite. The LLM critic prompt below runs as a second pass
when `OPENAI_API_KEY` is configured.

## Output critic prompt (LLM)

```text
SYSTEM:
You are a careful compliance guardrail.

USER:
You are a compliance assistant guardrail. Read the AI-generated audit
report below.
Return JSON of the form {"passed": bool, "reason": string, "safe_text": string}.
Set passed=false ONLY if the text gives unqualified legal advice
("you must", "you should"), cites a non-existent case, or guarantees a
legal outcome.
If passed=false, also produce a safe_text rewrite that hedges the
language to analysis only.
Otherwise return safe_text equal to the input verbatim.

--- REPORT START ---
<text>
--- REPORT END ---
```

## Input topic prompt (Colang skeleton)

See `services/guardrails_service/rails/auditor.co` for the Colang flows
covering: off-topic submissions, requests for legal advice, and output
legal-safety rewrites.

**Failure modes for v2 to attack:** false positives on the legitimate
word "must" inside non-prescriptive contexts, false negatives on
plausible-sounding invented case citations (`Greene v. Acme [2019]
EWHC 211`), and rejecting non-English contracts as off-topic.
