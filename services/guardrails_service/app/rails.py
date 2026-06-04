"""Rule-based guardrails + optional LLM critic.

We deliberately implement the rails as plain Python so the demo works on
Windows without NeMo Guardrails installed. A Colang config skeleton ships
alongside (`rails/auditor.co`) so the team can swap in NeMo later without
changing the FastAPI surface.

Two endpoints, mirroring the PDF spec:

* `check_input` ‑ is this a real legal contract?
   - rejects empty / very short text
   - rejects clearly off-topic content (recipes, marketing copy, etc.)
   - rejects offensive content via a simple deny-list

* `check_output` ‑ does the AI report stray into unqualified legal advice?
   - rejects (or rewrites) imperative legal directives
   - rejects fabricated case citations
   - hedges "this is illegal" -> "this clause appears inconsistent with..."

The LLM critic adds a second pass when `OPENAI_API_KEY` is configured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .config import settings


# ---------------------------------------------------------------------------
# Input rails
# ---------------------------------------------------------------------------

_CONTRACT_KEYWORDS = (
    "agreement",
    "party",
    "parties",
    "clause",
    "section",
    "hereby",
    "shall",
    "terms",
    "obligation",
    "indemnif",
    "liability",
    "confidential",
    "termination",
    "effective date",
    "whereas",
    "governing law",
)

_OFFTOPIC_INDICATORS = (
    "buy now",
    "limited time offer",
    "recipe",
    "preheat the oven",
    "follow me on",
    "subscribe to my",
    "free download",
)

_OFFENSIVE_PATTERNS = (
    re.compile(r"\b(fuck|shit|bitch|asshole)\b", re.IGNORECASE),
)


@dataclass
class _RuleHit:
    name: str
    reason: str


def _input_rules(text: str) -> list[_RuleHit]:
    hits: list[_RuleHit] = []
    stripped = text.strip()
    if len(stripped) < settings.min_input_chars:
        hits.append(
            _RuleHit(
                name="too_short",
                reason=(
                    f"Input is {len(stripped)} chars; "
                    f"a contract is expected to be at least {settings.min_input_chars} chars."
                ),
            )
        )
    if not any(kw in stripped.lower() for kw in _CONTRACT_KEYWORDS):
        hits.append(
            _RuleHit(
                name="missing_contract_signals",
                reason="No typical contract language detected (clause, party, shall, agreement, ...).",
            )
        )
    for indicator in _OFFTOPIC_INDICATORS:
        if indicator in stripped.lower():
            hits.append(
                _RuleHit(
                    name="offtopic_marker",
                    reason=f"Off-topic marker detected: '{indicator}'.",
                )
            )
            break
    for pat in _OFFENSIVE_PATTERNS:
        if pat.search(stripped):
            hits.append(_RuleHit(name="offensive_language", reason="Offensive language detected."))
            break
    return hits


def check_input(text: str) -> dict:
    hits = _input_rules(text)
    if not hits:
        return {"passed": True, "reason": None, "safe_text": None, "matched_rules": []}
    reason = "; ".join(h.reason for h in hits)
    return {
        "passed": False,
        "reason": reason,
        "safe_text": None,
        "matched_rules": [h.name for h in hits],
    }


# ---------------------------------------------------------------------------
# Output rails — "no unqualified legal advice"
# ---------------------------------------------------------------------------

_ADVICE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"\byou\s+must\s+", re.IGNORECASE),
        "directive_you_must",
        "this clause appears inconsistent with ",
    ),
    (
        re.compile(r"\byou\s+should\s+", re.IGNORECASE),
        "directive_you_should",
        "consider reviewing whether ",
    ),
    (
        re.compile(r"\bwe recommend that you\b", re.IGNORECASE),
        "directive_we_recommend",
        "a reviewer may want to consider whether ",
    ),
    (
        re.compile(r"\bthis is illegal\b", re.IGNORECASE),
        "definitive_legality",
        "this clause appears inconsistent with applicable regulation",
    ),
    (
        re.compile(r"\bthis is legal\b", re.IGNORECASE),
        "definitive_legality",
        "this clause appears consistent with the cited regulation",
    ),
    (
        re.compile(r"\bguarantee[ds]?\b", re.IGNORECASE),
        "guarantee_language",
        "may indicate",
    ),
]

_FABRICATED_CITATION = re.compile(
    r"\bSmith v\.?\s+\w+|\b\d{4}\s+WL\s+\d+|\b\[\d{4}\]\s+UKSC\b",
)


def _output_rules(text: str) -> tuple[list[_RuleHit], str]:
    hits: list[_RuleHit] = []
    rewritten = text
    for pattern, name, replacement in _ADVICE_PATTERNS:
        if pattern.search(rewritten):
            hits.append(_RuleHit(name=name, reason=f"Pattern '{pattern.pattern}' detected."))
            rewritten = pattern.sub(replacement, rewritten)
    if _FABRICATED_CITATION.search(rewritten):
        hits.append(_RuleHit(name="fabricated_citation", reason="Possible fabricated case citation."))
        rewritten = _FABRICATED_CITATION.sub("[citation removed by guardrail]", rewritten)
    return hits, rewritten


def check_output(text: str) -> dict:
    hits, rewritten = _output_rules(text)
    if not hits:
        return {"passed": True, "reason": None, "safe_text": text, "matched_rules": []}

    reason = "Output contained unqualified legal advice or fabricated citations; rewritten."
    return {
        "passed": True,  # we pass *after* rewriting; downstream sees safe_text
        "reason": reason,
        "safe_text": rewritten,
        "matched_rules": [h.name for h in hits],
    }


# ---------------------------------------------------------------------------
# Optional LLM critic — only used when OPENAI_API_KEY is configured.
# ---------------------------------------------------------------------------

_LLM_CRITIC_PROMPT = (
    "You are a compliance assistant guardrail. Read the AI-generated audit report below.\n"
    "Return JSON of the form {\"passed\": bool, \"reason\": string, \"safe_text\": string}.\n"
    "Set passed=false ONLY if the text gives unqualified legal advice "
    "(\"you must\", \"you should\"), cites a non-existent case, or guarantees a legal outcome.\n"
    "If passed=false, also produce a safe_text rewrite that hedges the language to analysis only.\n"
    "Otherwise return safe_text equal to the input verbatim.\n"
    "\n--- REPORT START ---\n{text}\n--- REPORT END ---"
)


def _extract_json(raw: str) -> dict:
    """Parse JSON from LLM output, tolerating markdown fences or extra text."""
    import json, re
    raw = raw.strip()
    # Strip markdown code fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Find the first {...} block in the text
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            return json.loads(m.group())
        raise


def _parse_critic_json(raw: str, original_text: str) -> dict:
    data = _extract_json(raw)
    return {
        "passed": bool(data.get("passed", True)),
        "reason": data.get("reason"),
        "safe_text": data.get("safe_text") or original_text,
        "matched_rules": ["llm_critic"] if not data.get("passed", True) else [],
    }


def _gemini_critic(text: str) -> Optional[dict]:
    if not settings.gemini_api_key:
        return None
    try:
        from google import genai  # type: ignore
        from google.genai import types as genai_types  # type: ignore

        client = genai.Client(api_key=settings.gemini_api_key)
        model_name = settings.gemini_model
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        resp = client.models.generate_content(
            model=model_name,
            contents=_LLM_CRITIC_PROMPT.replace("{text}", text),
            config=genai_types.GenerateContentConfig(
                system_instruction="You are a careful compliance guardrail.",
                temperature=0.0,
                max_output_tokens=2048,
            ),
        )
        return _parse_critic_json(resp.text or "{}", text)
    except Exception as exc:
        print(f"[guardrails] Gemini critic skipped: {exc!r}")
        return None


def _openai_critic(text: str) -> Optional[dict]:
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI
        import json

        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a careful compliance guardrail."},
                {"role": "user", "content": _LLM_CRITIC_PROMPT.replace("{text}", text)},
            ],
            temperature=0,
        )
        return _parse_critic_json(completion.choices[0].message.content or "{}", text)
    except Exception as exc:
        print(f"[guardrails] OpenAI critic skipped: {exc!r}")
        return None


def llm_critic(text: str) -> Optional[dict]:
    """Run the optional second-pass LLM critic. Returns None if unavailable."""
    if not (settings.enable_llm_critic and settings.has_llm):
        return None
    # Gemini preferred; OpenAI as fallback
    return _gemini_critic(text) or _openai_critic(text)
