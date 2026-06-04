"""Intent routing for the Compliance AI Assistant chat endpoint."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .chat_db_stats import is_db_stats_question, is_meta_query

_OFFTOPIC = (
    "tell me a joke",
    "joke",
    "recipe",
    "preheat the oven",
    "buy now",
    "limited time offer",
    "who won the game",
    "write a poem",
    "dating advice",
    "horoscope",
)

_PORTFOLIO_KW = (
    "total active contract",
    "how many contract",
    "how many bank",
    "how many cyber",
    "how many ai",
    "portfolio",
    "dataset",
    "xlsx",
    "excel",
    "contracts in the",
    "contracts in",
    "average sla",
    "contract manager",
    "supplier",
    "active contracts",
    "cybersecurity contract",
    "ai contract",
    "bank contract",
    "crowdstrike",
    "palo alto",
    "contract value",
    "total portfolio",
    "banking group",
)

_REGULATORY_KW = (
    "gdpr",
    "iso 27001",
    "iso27001",
    "hipaa",
    "pci",
    "sox",
    "regulation",
    "compliance",
    "obligation",
    "breach",
    "data subject",
    "article",
    "audit",
    "risk",
    "penalty",
    "fine",
)

_AUDIT_KW = (
    "this contract",
    "my upload",
    "uploaded contract",
    "last audit",
    "this audit",
    "the audit",
    "my audit",
    "finding",
    "findings",
    "clause_",
    "why was",
    "why is",
    "flagged",
    "non compliant",
    "non-compliant",
    "parties in",
    "who are the parties",
    "summarize finding",
    "summarise finding",
    "termination",
    "gap",
    "justification",
    "recommended correction",
    "report card",
    "bnk-",
)


@dataclass
class ChatRoute:
    intent: str  # off_topic | portfolio | regulatory | hybrid | audit | db_stats
    refused: bool = False
    refusal_message: str = ""
    inferred_category: Optional[str] = None


_REFUSAL_MSG = (
    "I can only answer **compliance and contract-portfolio** questions "
    "(regulations, audit obligations, dataset contracts). "
    "Please rephrase your question in that scope."
)


def _is_off_topic(q: str) -> bool:
    """Return True when the question is clearly unrelated to compliance/contracts."""
    for phrase in _OFFTOPIC:
        if phrase in q:
            return True
    # No compliance, contract, or regulatory keyword at all
    has_any = (
        any(k in q for k in _REGULATORY_KW)
        or any(k in q for k in _PORTFOLIO_KW)
        or any(k in q for k in _AUDIT_KW)
        or any(w in q for w in (
            "contract", "clause", "msa", "agreement", "vendor", "supplier",
            "gdpr", "regulation", "compliance", "audit", "finding", "risk",
            "law", "legal", "must", "shall", "require", "policy", "data",
            "bank", "finance", "cybersecurity", "security", "upload", "pdf",
        ))
    )
    return not has_any


def route_chat(
    question: str,
    contract_category: Optional[str] = None,
    audit_id: Optional[str] = None,
) -> ChatRoute:
    q = question.strip().lower()
    if len(q) < 3:
        return ChatRoute(
            intent="off_topic",
            refused=True,
            refusal_message="Please ask a compliance or contract-portfolio question.",
        )

    # Off-topic check runs FIRST — regardless of whether an audit is selected.
    if _is_off_topic(q):
        return ChatRoute(
            intent="off_topic",
            refused=True,
            refusal_message=_REFUSAL_MSG,
        )

    # DB-stats questions: counts/dates about uploaded audits → query SQLite directly.
    if is_db_stats_question(q):
        return ChatRoute(intent="db_stats")

    # Metadata queries: value, expiry, parties, jurisdiction → SQLite + parse_metadata.
    if is_meta_query(q):
        return ChatRoute(intent="meta_query")

    if audit_id:
        audit_score = sum(1 for k in _AUDIT_KW if k in q)
        reg_score = sum(1 for k in _REGULATORY_KW if k in q)
        port_score = sum(1 for k in _PORTFOLIO_KW if k in q)
        if reg_score > 0 and (audit_score > 0 or "?" in question):
            return ChatRoute(intent="hybrid", inferred_category=contract_category)
        if port_score > 0:
            return ChatRoute(intent="hybrid", inferred_category=contract_category)
        return ChatRoute(intent="audit", inferred_category=contract_category)

    cat = contract_category
    if not cat:
        if "bank" in q and "cyber" not in q and " ai " not in f" {q} ":
            cat = "bank"
        elif "cyber" in q or "security" in q and "contract" in q:
            cat = "cybersecurity"
        elif re.search(r"\bai\b", q) and "contract" in q:
            cat = "ai"

    audit_score = sum(1 for k in _AUDIT_KW if k in q)
    portfolio_score = sum(1 for k in _PORTFOLIO_KW if k in q)
    regulatory_score = sum(1 for k in _REGULATORY_KW if k in q)

    if audit_score > 0 and (regulatory_score > 0 or portfolio_score > 0):
        return ChatRoute(intent="hybrid", inferred_category=cat)
    if audit_score > 0:
        return ChatRoute(intent="audit", inferred_category=cat)

    if portfolio_score > 0 and regulatory_score > 0:
        return ChatRoute(intent="hybrid", inferred_category=cat)
    if portfolio_score > 0 or re.search(
        r"\b(how many|total|count|number of)\b.*\bcontract", q
    ):
        return ChatRoute(intent="portfolio", inferred_category=cat)

    if any(w in q for w in ("contract", "clause", "msa", "agreement", "vendor", "supplier")):
        if regulatory_score > 0 or portfolio_score > 0:
            return ChatRoute(intent="hybrid", inferred_category=cat)
        return ChatRoute(intent="portfolio", inferred_category=cat)

    if regulatory_score > 0 or "?" in question:
        return ChatRoute(intent="regulatory", inferred_category=cat)

    if any(w in q for w in ("must", "shall", "require", "legal", "law")):
        return ChatRoute(intent="regulatory", inferred_category=cat)

    return ChatRoute(
        intent="off_topic",
        refused=True,
        refusal_message=_REFUSAL_MSG,
    )
