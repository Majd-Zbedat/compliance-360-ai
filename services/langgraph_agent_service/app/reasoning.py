"""Per-clause compliance reasoning.

Decides {verdict, risk, justification, confidence} for a single contract
clause against the top-k matched regulatory clauses.

Two paths:

* LLM reasoning when `OPENAI_API_KEY` is configured. The system prompt
  ("Surface #2" in the prompt log) makes citation-grounding mandatory.

* Deterministic rule-based fallback used in offline mode. It is *not* a
  toy: it inspects the retrieval score, the clause-type tags, and a small
  set of "red-flag" patterns (no encryption, unlimited liability, no
  termination notice, unilateral amendments) to produce sensible risk
  assignments for demoing the dashboard without an API key.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from .config import settings


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class ReasoningInput:
    clause_id: str
    clause_text: str
    clause_type: str
    matches: list[dict]  # each has id, source, article, text, score


@dataclass
class ReasoningOutput:
    verdict: str  # compliant | non_compliant | ambiguous
    risk: str  # High | Medium | Low
    justification: str
    confidence: float  # 0..1
    matched_id: Optional[str]
    matched_source: Optional[str]
    matched_article: Optional[str]


# ---------------------------------------------------------------------------
# Rule-based path
# ---------------------------------------------------------------------------


_RED_FLAGS: dict[str, tuple[re.Pattern[str], str, str]] = {
    "no_encryption": (
        re.compile(r"\b(no|without)\b[^.]{0,40}\bencryption\b", re.IGNORECASE),
        "GDPR Art. 32 requires appropriate security measures including encryption.",
        "High",
    ),
    "unlimited_liability": (
        re.compile(r"\bunlimited liability\b|liability\s+is\s+unlimited", re.IGNORECASE),
        "Unlimited liability typically conflicts with local commercial caps.",
        "High",
    ),
    "no_notice_termination": (
        re.compile(r"terminate(d)?\s+(at any time|immediately)\b", re.IGNORECASE),
        "Termination without notice may violate mandatory notice periods.",
        "Medium",
    ),
    "unilateral_amendment": (
        re.compile(r"\bunilateral(ly)?\s+amend\b|may\s+modify[^.]{0,40}without\s+notice", re.IGNORECASE),
        "Unilateral amendment without renewed consent is typically unenforceable in consumer contracts.",
        "Medium",
    ),
    "indefinite_retention": (
        re.compile(r"retain(ed)?\s+(indefinitely|forever)", re.IGNORECASE),
        "Indefinite retention conflicts with GDPR Art. 5(1)(e) storage limitation.",
        "High",
    ),
    "broad_data_use": (
        re.compile(
            r"any\s+(and\s+all)?\s+data|every\s+field\s+about|all\s+purposes",
            re.IGNORECASE,
        ),
        "Overly broad data use conflicts with GDPR Art. 5(1)(c) data minimisation.",
        "Medium",
    ),
}


def _rule_based(input: ReasoningInput) -> ReasoningOutput:
    top = input.matches[0] if input.matches else None
    matched_id = top.get("id") if top else None
    matched_src = top.get("source") if top else None
    matched_art = top.get("article") if top else None

    text_lower = input.clause_text.lower()
    has_notice_period = bool(
        re.search(
            r"\d+\s*days?['\u2019]?\s*(written\s+)?notice|notice\s+period|written\s+notice",
            text_lower,
            re.IGNORECASE,
        )
    )

    triggered: list[tuple[str, str, str]] = []
    for name, (pattern, reason, severity) in _RED_FLAGS.items():
        if name == "no_notice_termination" and has_notice_period:
            continue
        if pattern.search(input.clause_text):
            triggered.append((name, reason, severity))

    if triggered:
        worst = "High" if any(s == "High" for _, _, s in triggered) else "Medium"
        why = "; ".join(reason for _, reason, _ in triggered)
        citation = f"Top retrieval: {matched_src} {matched_art}." if top else "No retrieval match available."
        return ReasoningOutput(
            verdict="non_compliant",
            risk=worst,
            justification=(
                f"Clause appears inconsistent with retrieved regulation. {why} {citation}"
            ),
            confidence=0.7 if worst == "High" else 0.55,
            matched_id=matched_id,
            matched_source=matched_src,
            matched_article=matched_art,
        )

    score = float((top or {}).get("score") or 0.0)
    if not top:
        return ReasoningOutput(
            verdict="ambiguous",
            risk="Low",
            justification="No relevant regulatory clause retrieved; manual review recommended.",
            confidence=0.3,
            matched_id=None,
            matched_source=None,
            matched_article=None,
        )

    if score >= 0.45:
        return ReasoningOutput(
            verdict="compliant",
            risk="Low",
            justification=(
                f"Clause aligns with retrieved {matched_src} {matched_art} "
                f"(similarity {score:.2f}); no red-flag patterns detected."
            ),
            confidence=min(0.6 + score / 2, 0.9),
            matched_id=matched_id,
            matched_source=matched_src,
            matched_article=matched_art,
        )

    return ReasoningOutput(
        verdict="ambiguous",
        risk="Medium",
        justification=(
            f"Closest retrieval ({matched_src} {matched_art}) only weakly matches "
            f"(similarity {score:.2f}); reviewer should validate."
        ),
        confidence=0.4,
        matched_id=matched_id,
        matched_source=matched_src,
        matched_article=matched_art,
    )


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


# Prompt Engineering Surface #2 - agent system prompt + tool descriptions.
# Versioned in shared/prompts/agent_reasoning_v1.md. Keep this string and the
# file in sync; the file is the source of truth for the log.
REASONING_SYSTEM_PROMPT = """You are a senior compliance analyst working in a regulated industry.
For a SINGLE contract clause and the top-k regulatory clauses retrieved by the RAG tool,
you must produce a structured verdict.

Strict rules:
1. You MUST cite the retrieved regulatory clause id, source, and article in your justification.
2. You MUST NOT invent regulatory references. If no retrieval matches, return verdict="ambiguous".
3. You MUST hedge: write "this clause appears inconsistent with..." NOT "this is illegal".
4. Risk is a function of likelihood + impact:
   - High: clear contradiction with mandatory regulation, breach notification, or unlimited liability.
   - Medium: weaker alignment, ambiguous phrasing, or partial coverage.
   - Low: clause aligns with retrieved regulation or is purely operational.

Return ONLY valid JSON:
{
  "verdict": "compliant" | "non_compliant" | "ambiguous",
  "risk": "High" | "Medium" | "Low",
  "justification": "<one or two sentences, MUST cite the regulatory id and article>",
  "confidence": <float in [0,1]>
}
"""


def _build_user_msg(input: ReasoningInput) -> str:
    retrieval_block = "\n".join(
        f"- id={m.get('id')} source={m.get('source')} article={m.get('article')} "
        f"score={m.get('score', 0.0):.2f}\n  text: {m.get('text', '')[:600]}"
        for m in input.matches
    )
    return (
        f"Clause type: {input.clause_type}\n"
        f"Clause text:\n{input.clause_text[:1500]}\n\n"
        f"Retrieved regulatory clauses (top-{len(input.matches)}):\n{retrieval_block}\n"
    )


def _extract_json(raw: str) -> dict:
    """Parse JSON from LLM output, tolerating markdown fences or extra text."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            return json.loads(m.group())
        raise


def _parse_llm_json(raw: str, matches: list[dict]) -> ReasoningOutput:
    data = _extract_json(raw)
    verdict = str(data.get("verdict", "ambiguous"))
    risk = str(data.get("risk", "Low"))
    top = matches[0] if matches else None
    return ReasoningOutput(
        verdict=verdict if verdict in {"compliant", "non_compliant", "ambiguous"} else "ambiguous",
        risk=risk if risk in {"High", "Medium", "Low"} else "Low",
        justification=str(data.get("justification", "")),
        confidence=float(data.get("confidence", 0.5)),
        matched_id=(top or {}).get("id"),
        matched_source=(top or {}).get("source"),
        matched_article=(top or {}).get("article"),
    )


def _gemini_reason(input: ReasoningInput) -> Optional[ReasoningOutput]:
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
            contents=_build_user_msg(input),
            config=genai_types.GenerateContentConfig(
                system_instruction=REASONING_SYSTEM_PROMPT,
                temperature=0.0,
                max_output_tokens=2048,
            ),
        )
        return _parse_llm_json(resp.text or "{}", input.matches)
    except Exception as exc:
        print(f"[agent] Gemini reasoning skipped: {exc!r}")
        return None


def _openai_reason(input: ReasoningInput) -> Optional[ReasoningOutput]:
    if not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_msg(input)},
            ],
        )
        return _parse_llm_json(completion.choices[0].message.content or "{}", input.matches)
    except Exception as exc:
        print(f"[agent] OpenAI reasoning skipped: {exc!r}")
        return None


def _llm_reason(input: ReasoningInput) -> Optional[ReasoningOutput]:
    if not (settings.enable_llm_reasoning and settings.has_llm):
        return None
    # Gemini preferred; OpenAI as fallback
    return _gemini_reason(input) or _openai_reason(input)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def reason(input: ReasoningInput) -> ReasoningOutput:
    return _llm_reason(input) or _rule_based(input)
