"""Database statistics answerer for the Compliance AI chat endpoint.

Handles structured questions about uploaded/analyzed contracts that need
direct database queries instead of vector similarity search, e.g.:

  - "how many contracts were uploaded between Jun 3 and Jun 4?"
  - "how many active contracts do we have?"
  - "how many high-risk audits this week?"
  - "when was the last upload?"
  - "how many contracts were analyzed today?"
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

from .db import AuditRow, session_scope
from .audit_enrichment import parse_contract_metadata


# ---------------------------------------------------------------------------
# Detection — is this a DB-stats question?
# ---------------------------------------------------------------------------

_META_QUERY_PATTERNS = [
    r"\b(most|highest|largest|biggest|most expensive)\b.{0,40}\b(value|valued|expensive|worth|cost)\b",
    r"\b(most expensive|highest.?value|largest.?value|biggest.?contract)\b",
    r"\bcontract.{0,30}\b(value|worth|cost|price|amount)\b",
    r"\b(value|worth|cost).{0,30}\bcontract\b",
    r"\b(expir|expire|expiry).{0,40}\b(contract|audit|when|date)\b",
    r"\bcontract.{0,30}\b(expir|expire|expiry)\b",
    r"\bwhich contract.{0,60}\b(expensive|valuable|highest|largest|cheapest|lowest)\b",
    r"\b(cheapest|lowest.?value|smallest.?contract)\b",
    r"\bcontract.{0,30}\b(manager|managed by)\b",
    r"\b(who|what).{0,20}\b(manage|manages|managing)\b.{0,20}\bcontract\b",
    r"\bparty [ab]\b.{0,40}\bcontract\b",
    r"\bcontract.{0,30}\bparty\b",
    r"\bjurisdiction\b",
    r"\bgoverning law\b",
    r"\bgoverned by\b",
    r"\bpayment terms?\b",
    r"\bnet \d+\b.{0,20}\bcontract\b",
    r"\bwhich contract.{0,60}\b(jurisdiction|party|value|expir|risk)\b",
    r"\bdetails?.{0,20}\bcontract\b",
    r"\bcontract.{0,30}\bdetails?\b",
    r"\b(list|show|what are).{0,30}\b(all\s+)?contracts?\b",
    r"\bcontracts?.{0,30}(expir|active|approved|rejected|pending).{0,30}(in|on|by|at)\b",
    # Contract ID lookup patterns
    r"\bcontract\s+(id|number|no\.?|#)\s*[=:—\-]?\s*[A-Z0-9]",
    r"\bid\s*[=:—]\s*[A-Z0-9\-]{3,}",
    r"\b[A-Z]{2,8}-\d{4}-[A-Z0-9]{2,12}\b",  # matches IDs like BNK-2026-026, DEMO-2026-001
    r"\b(find|lookup|look up|get|show|tell me about|details (for|of|about))\b.{0,40}\b[A-Z]{2,8}-\d{4}",
    r"\bwhat.{0,40}\bcontract\b.{0,40}\b[A-Z]{2,8}-\d{4}",
    # Contract term / duration comparisons
    r"\b(longest|shortest)\b.{0,40}\b(term|duration|contract|period|tenure)\b",
    r"\bcontract.{0,40}\b(longest|shortest|duration|term length|tenure)\b",
    r"\b(how long|duration|term length)\b.{0,30}\bcontract\b",
]

_META_COMPILED = [re.compile(p, re.IGNORECASE) for p in _META_QUERY_PATTERNS]


def is_meta_query(q: str) -> bool:
    """Return True if the question needs structured contract metadata."""
    return any(p.search(q) for p in _META_COMPILED)


_DB_STATS_PATTERNS = [
    r"\bhow many\b.{0,60}\bcontracts?\b",
    r"\bhow many\b.{0,60}\baudits?\b",
    r"\bhow many\b.{0,60}\b(document|upload|file)s?\b",
    r"\b(count|number of)\b.{0,40}\bcontracts?\b",
    r"\b(count|number of)\b.{0,40}\baudits?\b",
    r"\b(active|high.?risk|medium.?risk|low.?risk)\b.{0,30}\bcontracts?\b",
    r"\b(active|high.?risk|medium.?risk|low.?risk)\b.{0,30}\baudits?\b",
    r"\b(uploaded|submitted|analyz|process)\b.{0,40}\b(between|from|since|today|yesterday|this week|last week)\b",
    r"\b(between|from)\b.{0,60}\b(to|and)\b.{0,60}\bcontracts?\b",
    r"\b(between|from)\b.{0,60}\b(to|and)\b.{0,60}\baudits?\b",
    r"\bhow many\b.{0,60}\b(between|from|since|today|yesterday)\b",
    r"\bwhen\b.{0,20}\b(last|latest|most recent)\b.{0,20}\b(upload|audit|contract)\b",
    r"\b(last|latest|most recent)\b.{0,20}\b(upload|audit|contract)\b",
    r"\b(total|count)\b.{0,20}\bcontracts?\b",
    r"\bhow many\b.{0,30}\b(high|medium|low|active|pending|rejected)\b",
    r"\bcontracts?\b.{0,30}\b(between|from|since|on|today|yesterday)\b",
]

_DB_STATS_COMPILED = [re.compile(p, re.IGNORECASE) for p in _DB_STATS_PATTERNS]


def is_db_stats_question(q: str) -> bool:
    """Return True if the question is about database counts / upload stats."""
    return any(p.search(q) for p in _DB_STATS_COMPILED)


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_REF_YEAR = 2026


def _parse_date_token(text: str) -> Optional[datetime]:
    """Parse a single date token like 'Jun 3', '3 Jun', '2026-06-03', 'today'."""
    text = text.strip().lower()
    now = datetime.utcnow()
    if text in ("today", "now"):
        d = now.date()
        return datetime(d.year, d.month, d.day)
    if text == "yesterday":
        d = (now - timedelta(days=1)).date()
        return datetime(d.year, d.month, d.day)

    # ISO: 2026-06-03
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    # "Jun 3" or "June 3" (optional year)
    m = re.match(r"([a-z]+)\s+(\d{1,2})(?:\s*,?\s*(\d{4}))?", text)
    if m:
        month = _MONTH_MAP.get(m.group(1))
        if month:
            return datetime(int(m.group(3)) if m.group(3) else _REF_YEAR, month, int(m.group(2)))

    # "3 Jun" or "3 June" (optional year)
    m = re.match(r"(\d{1,2})\s+([a-z]+)(?:\s*,?\s*(\d{4}))?", text)
    if m:
        month = _MONTH_MAP.get(m.group(2))
        if month:
            return datetime(int(m.group(3)) if m.group(3) else _REF_YEAR, month, int(m.group(1)))

    return None


def _end_of_day(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, dt.day, 23, 59, 59)


def _extract_date_range(q: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """Extract a (start, end) datetime range from the question text."""
    now = datetime.utcnow()
    q_l = q.lower()

    if "this week" in q_l:
        start = now - timedelta(days=now.weekday())
        return datetime(start.year, start.month, start.day), now

    if "last week" in q_l:
        end = now - timedelta(days=now.weekday())
        start = end - timedelta(days=7)
        return start, end

    if "today" in q_l and "between" not in q_l and "from" not in q_l:
        d = now.date()
        return datetime(d.year, d.month, d.day), now

    if "yesterday" in q_l and "between" not in q_l and "from" not in q_l:
        d = (now - timedelta(days=1)).date()
        return datetime(d.year, d.month, d.day), _end_of_day(datetime(d.year, d.month, d.day))

    # "between X and Y" / "from X to Y"
    rng = re.search(
        r"(?:between|from)\s+(.+?)\s+(?:to|and)\s+(.+?)(?:\s*[\?!,]|$)",
        q_l,
    )
    if rng:
        d1 = _parse_date_token(rng.group(1).strip())
        d2 = _parse_date_token(rng.group(2).strip())
        if d1 and d2:
            return d1, _end_of_day(d2)

    # "since X"
    since = re.search(r"\bsince\s+(.+?)(?:\s*[\?!,]|$)", q_l)
    if since:
        d1 = _parse_date_token(since.group(1).strip())
        if d1:
            return d1, now

    # "on X"
    on = re.search(r"\bon\s+([a-z]+ \d{1,2}|\d{1,2} [a-z]+)(?:\s*[\?!,]|$)", q_l)
    if on:
        d1 = _parse_date_token(on.group(1).strip())
        if d1:
            return d1, _end_of_day(d1)

    return None, None


# ---------------------------------------------------------------------------
# Metadata extraction helpers
# ---------------------------------------------------------------------------

def _parse_numeric_value(val_str: str) -> Optional[float]:
    """Extract numeric value from strings like 'USD $1,280,000' → 1280000.0"""
    if not val_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", val_str.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _infer_category(c: dict) -> Optional[str]:
    """Infer a portfolio category (cybersecurity / bank / ai) for an uploaded contract."""
    blob = " ".join(
        str(c.get(k) or "")
        for k in ("contract_type", "filename", "party_b", "party_b_regulated_by", "party_a")
    ).lower()
    if any(w in blob for w in ("cyber", "security", "soc 2", "soc2", "iso 27001", "iso27001", "infosec", "threat", "nist")):
        return "cybersecurity"
    if any(w in blob for w in ("bank", "financial", "finance", "basel", "apra", "occ", "fdic", "lei")):
        return "bank"
    if re.search(r"\bai\b|artificial intelligence|machine learning|\bmodel\b|\bllm\b", blob):
        return "ai"
    return None


def _detect_question_category(q: str) -> Optional[str]:
    """Detect which contract category the user is asking about, if any."""
    if re.search(r"\b(cyber|cybersecurity|security|infosec)\b", q):
        return "cybersecurity"
    if re.search(r"\b(banking|bank|financial|finance)\b", q):
        return "bank"
    if re.search(r"\b(ai|a\.i\.|artificial intelligence|machine learning)\b", q):
        return "ai"
    return None


def _parse_flexible_date(s: str) -> Optional[datetime]:
    """Parse contract date strings like 'June 1, 2026', '2026-06-01', 'Jun 1 2026'."""
    if not s:
        return None
    return _parse_date_token(s.strip().lower())


def _contract_duration_days(c: dict) -> Optional[int]:
    """Compute contract term length in days from effective → expiry dates."""
    eff = _parse_flexible_date(c.get("effective_date") or "")
    exp = _parse_flexible_date(c.get("expiry_date") or "")
    if eff and exp and exp > eff:
        return (exp - eff).days
    return None


def _fmt_duration(days: int) -> str:
    """Human-readable duration, e.g. 730 → '24 months (~2.0 years)'."""
    months = round(days / 30.44)
    years = days / 365.25
    return f"{months} months (~{years:.1f} years)"


def _load_all_metadata(*, dedupe: bool = True) -> list[dict]:
    """Load all audits with their parsed contract metadata — cached per-call.

    When ``dedupe`` is True, only the most recent audit per contract
    (keyed by contract number or filename) is returned so aggregate answers
    don't repeat the same contract when a file was re-uploaded several times.
    """
    with session_scope() as s:
        rows = s.query(AuditRow).order_by(AuditRow.created_at.desc()).all()
        result = []
        seen_keys: set[str] = set()
        for r in rows:
            meta = parse_contract_metadata(list(r.clauses or []))
            if dedupe:
                key = (r.filename or meta.get("contract_number") or r.id).strip().lower()
                if key in seen_keys:
                    continue
                seen_keys.add(key)
            result.append({
                "id": r.id,
                "filename": r.filename,
                "status": r.status,
                "review_status": r.review_status,
                "overall_risk": r.overall_risk or "Unknown",
                "created_at": r.created_at,
                "contract_number": meta.get("contract_number"),
                "contract_value": meta.get("contract_value"),
                "contract_value_num": _parse_numeric_value(meta.get("contract_value") or ""),
                "effective_date": meta.get("effective_date"),
                "expiry_date": meta.get("expiry_date"),
                "jurisdiction": meta.get("jurisdiction") or r.jurisdiction,
                "governing_law": meta.get("governing_law"),
                "payment_terms": meta.get("payment_terms"),
                "contract_manager": meta.get("contract_manager"),
                "party_a": meta.get("party_a"),
                "party_a_regulated_by": meta.get("party_a_regulated_by"),
                "party_b": meta.get("party_b"),
                "party_b_regulated_by": meta.get("party_b_regulated_by"),
                "contract_type": r.contract_type,
                "parties": list(r.parties or []),
            })
    return result


def _fmt_contract_line(c: dict, *, show_value: bool = True) -> str:
    parts = [f"**`{c['filename']}`**"]
    if show_value and c.get("contract_value"):
        parts.append(f"value: {c['contract_value']}")
    if c.get("contract_number"):
        parts.append(f"ID: {c['contract_number']}")
    if c.get("overall_risk"):
        parts.append(f"risk: {c['overall_risk']}")
    if c.get("expiry_date"):
        parts.append(f"expires: {c['expiry_date']}")
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Metadata query answerer
# ---------------------------------------------------------------------------

def _extract_contract_id(question: str) -> Optional[str]:
    """Extract a contract ID like BNK-2026-026 or DEMO-2026-001 from a question."""
    # Match standard contract ID format: 2-8 uppercase letters + year + alphanumeric suffix
    m = re.search(r"\b([A-Z]{2,8}-\d{4}-[A-Z0-9]{2,12})\b", question, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Also match "id = XYZ" or "id: XYZ" patterns where XYZ may be non-standard
    m = re.search(r"\b(?:contract\s+)?(?:id|number|no\.?|#)\s*[=:\-–—]\s*([A-Z0-9][A-Z0-9\-/]{2,30})", question, re.IGNORECASE)
    if m:
        return m.group(1).upper().strip("-")
    return None


def _fmt_full_contract(c: dict) -> str:
    """Format a full contract detail block."""
    lines: list[str] = []
    lines.append(f"### Contract: `{c['filename']}`")
    lines.append("")
    if c.get("contract_number"):
        lines.append(f"**Contract ID:** {c['contract_number']}")
    if c.get("contract_value"):
        lines.append(f"**Contract Value:** {c['contract_value']}")
    if c.get("effective_date"):
        lines.append(f"**Effective Date:** {c['effective_date']}")
    if c.get("expiry_date"):
        lines.append(f"**Expiry Date:** {c['expiry_date']}")
    if c.get("contract_manager"):
        lines.append(f"**Contract Manager:** {c['contract_manager']}")
    if c.get("payment_terms"):
        lines.append(f"**Payment Terms:** {c['payment_terms']}")
    if c.get("jurisdiction") or c.get("governing_law"):
        lines.append(f"**Jurisdiction:** {c.get('jurisdiction') or c.get('governing_law')}")
    if c.get("contract_type"):
        lines.append(f"**Contract Type:** {c['contract_type']}")
    lines.append(f"**Overall Risk:** {c['overall_risk']}")
    lines.append(f"**Review Status:** {c.get('review_status') or 'Pending'}")
    if c.get("status"):
        lines.append(f"**Status:** {c['status']}")
    if c.get("party_a"):
        pa_line = f"**Party A:** {c['party_a']}"
        if c.get("party_a_regulated_by"):
            pa_line += f" (Regulated by: {c['party_a_regulated_by']})"
        lines.append(pa_line)
    if c.get("party_b"):
        pb_line = f"**Party B:** {c['party_b']}"
        if c.get("party_b_regulated_by"):
            pb_line += f" (Regulated by: {c['party_b_regulated_by']})"
        lines.append(pb_line)
    elif c.get("parties"):
        lines.append(f"**Parties:** {', '.join(c['parties'])}")
    lines.append(f"\n_Uploaded: {c['created_at'].strftime('%b %d, %Y') if c.get('created_at') else '—'}_")
    return "\n".join(lines)


def _extract_specific_field(q: str, c: dict) -> Optional[str]:
    """If the question targets a single field of a contract, return just that value."""
    name = f"`{c['filename']}`"

    if re.search(r"\b(contract manager|who manages|who is the manager|managed by)\b", q):
        v = c.get("contract_manager")
        return f"The contract manager for {name} is **{v}**." if v else f"No contract manager found for {name}."

    if re.search(r"\b(contract value|how much|worth|price|amount|value)\b", q):
        v = c.get("contract_value")
        return f"The contract value of {name} is **{v}**." if v else f"No contract value found for {name}."

    if re.search(r"\b(expir|expire|expiry|end date|ends)\b", q):
        v = c.get("expiry_date")
        return f"The expiry date of {name} is **{v}**." if v else f"No expiry date found for {name}."

    if re.search(r"\b(effective date|start date|commence|begins|started)\b", q):
        v = c.get("effective_date")
        return f"The effective date of {name} is **{v}**." if v else f"No effective date found for {name}."

    if re.search(r"\b(payment terms?|net \d+|how.*paid|invoice)\b", q):
        v = c.get("payment_terms")
        return f"The payment terms for {name} are **{v}**." if v else f"No payment terms found for {name}."

    if re.search(r"\b(jurisdiction|governing law|governed by)\b", q):
        v = c.get("jurisdiction") or c.get("governing_law")
        return f"The jurisdiction of {name} is **{v}**." if v else f"No jurisdiction found for {name}."

    if re.search(r"\b(party a|engaging institution|client side)\b", q):
        v = c.get("party_a")
        return f"Party A of {name} is **{v}**." if v else f"No Party A found for {name}."

    if re.search(r"\b(party b|service provider|vendor side)\b", q):
        v = c.get("party_b")
        return f"Party B of {name} is **{v}**." if v else f"No Party B found for {name}."

    if re.search(r"\b(parties|who are the parties|contracting parties)\b", q):
        pa = c.get("party_a") or "—"
        pb = c.get("party_b") or (", ".join(c.get("parties") or [])) or "—"
        return f"Parties in {name}:\n  • Party A: **{pa}**\n  • Party B: **{pb}**"

    if re.search(r"\b(risk|risk level|overall risk)\b", q):
        return f"The overall risk of {name} is **{c['overall_risk']}**."

    if re.search(r"\b(status|review status|review decision)\b", q):
        return f"Review status of {name}: **{c.get('review_status') or 'Pending'}** (pipeline status: {c['status']})."

    return None  # No specific field matched → caller shows full details


def answer_meta_query(question: str) -> Optional[str]:
    """Answer a structured metadata question about contracts. Returns None if not handled."""
    q = question.strip().lower()
    contracts = _load_all_metadata()
    if not contracts:
        return "No contract audits found. Upload a contract to get started."

    # ── Contract ID lookup (highest priority) ─────────────────────────────
    cid = _extract_contract_id(question)
    if cid:
        # Search by contract_number field first, then filename
        matched = [
            c for c in contracts
            if (c.get("contract_number") or "").upper() == cid
            or cid in (c.get("contract_number") or "").upper()
            or cid.lower() in c["filename"].lower()
        ]
        if matched:
            hit = matched[0]
            # If asking for a specific field, return just that field value
            specific = _extract_specific_field(q, hit)
            if specific:
                return specific
            # Generic / "details" question → full card
            if len(matched) == 1:
                return _fmt_full_contract(hit)
            lines = [f"**{len(matched)}** contract(s) matching ID **{cid}**:"]
            for c in matched[:3]:
                lines.append(f"\n{_fmt_full_contract(c)}")
            return "\n".join(lines)
        # No match — try partial filename
        partial = [c for c in contracts if any(part in c["filename"].upper() for part in cid.split("-")[:2])]
        if partial:
            lines = [f"No exact match for **{cid}**. Closest contracts found:"]
            for c in partial[:3]:
                lines.append(f"  • `{c['filename']}` (ID: {c.get('contract_number') or '—'})")
            return "\n".join(lines)
        known = ", ".join(f"`{c['contract_number']}`" for c in contracts if c.get("contract_number"))
        return (
            f"No contract found with ID **{cid}**. "
            + (f"Available IDs: {known[:300]}" if known else "No contract IDs extracted yet.")
        )

    # ── Category scoping ───────────────────────────────────────────────────
    # If the user names a category (e.g. "security contracts"), restrict all
    # aggregate answers below to that category only.
    cat = _detect_question_category(q)
    cat_label = ""
    if cat:
        scoped = [c for c in contracts if _infer_category(c) == cat]
        if scoped:
            contracts = scoped
            cat_label = f" (in the **{cat}** portfolio)"
        # If nothing matches the category, fall back to all contracts silently.

    # ── Longest / shortest contract term ───────────────────────────────────
    if re.search(r"\b(longest|shortest|duration|term length|how long)\b", q) and re.search(
        r"\b(term|duration|contract|period|tenure|long)\b", q
    ):
        is_longest = not bool(re.search(r"\b(shortest|smallest|least)\b", q))
        dated = [(d, c) for c in contracts if (d := _contract_duration_days(c))]
        if not dated:
            return (
                "No contract has both an effective date and expiry date parsed, "
                "so I can't compare term lengths yet."
            )
        ranked = sorted(dated, key=lambda t: t[0], reverse=is_longest)
        dur, top = ranked[0]
        label = "longest" if is_longest else "shortest"
        lines = [
            f"The **{label}-term contract**{cat_label} is **`{top['filename']}`** — "
            f"**{_fmt_duration(dur)}** ({top.get('effective_date')} → {top.get('expiry_date')})."
        ]
        if len(ranked) > 1:
            lines.append("\nBy term length:")
            for d, c in ranked[:6]:
                lines.append(f"  • `{c['filename']}` — {_fmt_duration(d)}")
        return "\n".join(lines)

    # ── Most / least expensive ─────────────────────────────────────────────
    is_most = bool(re.search(r"\b(most expensive|highest.?value|largest|biggest|most valuable)\b", q))
    is_least = bool(re.search(r"\b(cheapest|least expensive|lowest.?value|smallest)\b", q))
    if is_most or is_least:
        valued = [c for c in contracts if c["contract_value_num"]]
        if not valued:
            return "No contract values found in the analyzed contracts. Ensure contracts include a 'Contract Value' field."
        ranked = sorted(valued, key=lambda c: c["contract_value_num"], reverse=is_most)
        top = ranked[0]
        label = "most expensive" if is_most else "cheapest"
        lines = [f"The **{label} contract**{cat_label} is {_fmt_contract_line(top)}."]
        if len(ranked) > 1:
            lines.append("\nAll contracts by value:")
            for i, c in enumerate(ranked[:8], 1):
                lines.append(f"  {i}. {_fmt_contract_line(c)}")
        return "\n".join(lines)

    # ── Contract value query (general) ────────────────────────────────────
    if re.search(r"\bcontract.{0,30}\bvalue\b|\bvalue.{0,30}\bcontract\b", q):
        valued = [c for c in contracts if c["contract_value_num"]]
        no_value = [c for c in contracts if not c["contract_value_num"]]
        if not valued:
            return "No contract value data found. Ensure contracts include a 'Contract Value' field in the header."
        lines = [f"**{len(valued)}** contract(s) with known values:"]
        for c in sorted(valued, key=lambda x: x["contract_value_num"], reverse=True)[:8]:
            lines.append(f"  • {_fmt_contract_line(c)}")
        if no_value:
            lines.append(f"\n_{len(no_value)} contract(s) have no parseable value._")
        return "\n".join(lines)

    # ── Expiry / expiring ─────────────────────────────────────────────────
    if re.search(r"\b(expir|expire|expiry)\b", q):
        year_m = re.search(r"\b(202\d)\b", q)
        year_filter = year_m.group(1) if year_m else None
        with_expiry = [c for c in contracts if c.get("expiry_date")]
        if year_filter:
            with_expiry = [c for c in with_expiry if year_filter in (c["expiry_date"] or "")]
            lines = [f"**{len(with_expiry)}** contract(s) expiring in **{year_filter}**:"]
        else:
            lines = [f"**{len(with_expiry)}** contract(s) with expiry dates:"]
        for c in with_expiry[:8]:
            lines.append(f"  • `{c['filename']}` — expires **{c['expiry_date']}** ({c['overall_risk']} risk)")
        return "\n".join(lines)

    # ── Party / parties search ────────────────────────────────────────────
    if re.search(r"\bpart(y|ies)\b", q) or re.search(r"\b(who are|what companies|vendor|supplier)\b", q):
        # Try to find a name mentioned in the question
        name_m = re.search(r"(?:party|parties|for|with|by)\s+[\"']?([A-Z][A-Za-z\s&,\.]{3,40})[\"']?", question)
        search_name = name_m.group(1).lower().strip() if name_m else None
        if search_name:
            matched = [c for c in contracts if
                       search_name in (c.get("party_a") or "").lower() or
                       search_name in (c.get("party_b") or "").lower() or
                       any(search_name in p.lower() for p in c.get("parties") or [])]
            if matched:
                lines = [f"**{len(matched)}** contract(s) involving **{name_m.group(1)}**:"]
                for c in matched[:8]:
                    lines.append(f"  • `{c['filename']}` | Party A: {c.get('party_a') or '—'} | Party B: {c.get('party_b') or '—'}")
                return "\n".join(lines)
        # General parties list
        lines = ["**Parties in analyzed contracts:**"]
        for c in contracts[:10]:
            pa = c.get("party_a") or "—"
            pb = c.get("party_b") or (", ".join(c["parties"]) if c["parties"] else "—")
            lines.append(f"  • `{c['filename']}`: {pa} / {pb}")
        return "\n".join(lines)

    # ── Jurisdiction ──────────────────────────────────────────────────────
    if re.search(r"\bjurisdiction\b|\bgoverning law\b|\bgoverned by\b", q):
        by_jur: dict[str, list[str]] = {}
        for c in contracts:
            jur = c.get("jurisdiction") or c.get("governing_law") or "Unknown"
            by_jur.setdefault(jur, []).append(c["filename"])
        lines = ["**Contracts by jurisdiction:**"]
        for jur, files in sorted(by_jur.items(), key=lambda x: -len(x[1])):
            lines.append(f"  • **{jur}** ({len(files)}): " + ", ".join(f"`{f}`" for f in files[:3]))
        return "\n".join(lines)

    # ── Contract manager ─────────────────────────────────────────────────
    if re.search(r"\bcontract manager\b|\bmanaged by\b|\bwho manages\b", q):
        lines = ["**Contract managers:**"]
        for c in contracts:
            if c.get("contract_manager"):
                lines.append(f"  • `{c['filename']}` — **{c['contract_manager']}**")
        if len(lines) == 1:
            return "No contract manager data found in analyzed contracts."
        return "\n".join(lines)

    # ── Payment terms ────────────────────────────────────────────────────
    if re.search(r"\bpayment terms?\b|\bnet \d+\b", q):
        lines = ["**Payment terms by contract:**"]
        for c in contracts:
            if c.get("payment_terms"):
                lines.append(f"  • `{c['filename']}` — **{c['payment_terms']}**")
        if len(lines) == 1:
            return "No payment terms data found in analyzed contracts."
        return "\n".join(lines)

    # ── General "list all / show all contracts" ───────────────────────────
    if re.search(r"\b(list|show|what are).{0,20}(all\s+)?contracts?\b", q):
        lines = [f"**{len(contracts)}** analyzed contracts{cat_label}:\n"]
        for c in contracts[:15]:
            risk_label = f"[{c['overall_risk']}]"
            value = f" | {c['contract_value']}" if c.get("contract_value") else ""
            lines.append(f"  • {risk_label} `{c['filename']}`{value}")
        if len(contracts) > 15:
            lines.append(f"_... and {len(contracts) - 15} more._")
        return "\n".join(lines)

    return None  # Not handled — fall through to regular answering


# ---------------------------------------------------------------------------
# Main answerer
# ---------------------------------------------------------------------------

def _rows_to_snapshots(session) -> list[dict]:
    """Read all audit rows as plain dicts (safe outside session)."""
    all_rows = session.query(AuditRow).order_by(AuditRow.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "status": r.status,
            "overall_risk": r.overall_risk or "Unknown",
            "created_at": r.created_at,
            "contract_type": r.contract_type,
            "findings_count": len(r.findings or []),
            "high_findings": sum(1 for f in (r.findings or []) if f.get("risk") == "High"),
        }
        for r in all_rows
    ]


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%b %d, %Y")


def _fmt_files(rows: list[dict], limit: int = 6) -> str:
    seen: list[str] = []
    for r in rows:
        if r["filename"] not in seen:
            seen.append(r["filename"])
        if len(seen) >= limit:
            break
    return ", ".join(f"`{f}`" for f in seen)


def answer_db_stats(question: str) -> str:
    """Query the SQLite audit database and return a markdown-formatted answer."""
    q = question.strip().lower()

    with session_scope() as s:
        rows = _rows_to_snapshots(s)

    if not rows:
        return "No contract audits have been run yet. Upload a PDF to get started."

    total_all = len(rows)

    # ── Category scoping (e.g. "how many security contracts") ──────────────
    cat = _detect_question_category(q)
    cat_label = ""
    if cat:
        scoped = [r for r in rows if _infer_category(r) == cat]
        if scoped:
            rows = scoped
            total_all = len(rows)
            cat_label = f" in the **{cat}** portfolio"

    # ── Date range filter ──────────────────────────────────────────────────
    date_start, date_end = _extract_date_range(question)
    if date_start and date_end:
        filtered = [r for r in rows if date_start <= r["created_at"] <= date_end]
        date_label = f" between **{_fmt_date(date_start)}** and **{_fmt_date(date_end)}**"
    elif date_start:
        filtered = [r for r in rows if r["created_at"] >= date_start]
        date_label = f" since **{_fmt_date(date_start)}**"
    else:
        filtered = rows
        date_label = ""

    # ── "when was the last / most recent upload" ──────────────────────────
    if re.search(r"\b(last|latest|most recent)\b.{0,30}\b(upload|audit|contract|document)\b", q):
        if rows:
            latest = rows[0]  # already ordered DESC
            return (
                f"The most recent contract audit is **`{latest['filename']}`** "
                f"({latest['overall_risk']} risk, status: {latest['status']}), "
                f"uploaded on **{latest['created_at'].strftime('%B %d, %Y at %H:%M UTC')}**."
            )

    # ── Risk-level filter ─────────────────────────────────────────────────
    risk_filter: Optional[str] = None
    if re.search(r"\bhigh.?risk\b", q):
        risk_filter = "High"
    elif re.search(r"\bmedium.?risk\b", q):
        risk_filter = "Medium"
    elif re.search(r"\blow.?risk\b", q):
        risk_filter = "Low"

    if risk_filter:
        target = [r for r in filtered if r["overall_risk"] == risk_filter]
        count = len(target)
        lines = [
            f"**{count}** {risk_filter.lower()}-risk contract audit(s){date_label} "
            f"(out of {len(filtered)} total)."
        ]
        if target:
            lines.append("Files: " + _fmt_files(target))
        return "\n".join(lines)

    # ── Status filters ────────────────────────────────────────────────────
    if re.search(r"\bactive\b", q):
        target = [r for r in filtered if r["status"] != "Rejected"]
        count = len(target)
        by_status: dict[str, int] = {}
        for r in target:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        lines = [f"**{count}** active contract audit(s){date_label}."]
        for st, n in sorted(by_status.items()):
            lines.append(f"  • **{st}**: {n}")
        if target:
            lines.append("Files: " + _fmt_files(target))
        return "\n".join(lines)

    if re.search(r"\bpending\b|\bin review\b", q):
        target = [r for r in filtered if r["status"] == "Review"]
        lines = [f"**{len(target)}** contract audit(s) are currently pending review{date_label}."]
        if target:
            lines.append("Files: " + _fmt_files(target))
        return "\n".join(lines)

    if re.search(r"\brejected\b", q):
        target = [r for r in filtered if r["status"] == "Rejected"]
        lines = [f"**{len(target)}** contract audit(s) were rejected{date_label}."]
        if target:
            lines.append("Files: " + _fmt_files(target))
        return "\n".join(lines)

    if re.search(r"\bdone\b|\bcomplet\b|\banalyz\b", q):
        target = [r for r in filtered if r["status"] == "Done"]
        lines = [f"**{len(target)}** contract audit(s) completed{date_label}."]
        if target:
            lines.append("Files: " + _fmt_files(target))
        return "\n".join(lines)

    # ── General count (how many contracts / audits) ────────────────────────
    count = len(filtered)
    by_risk: dict[str, int] = {}
    for r in filtered:
        by_risk[r["overall_risk"]] = by_risk.get(r["overall_risk"], 0) + 1

    _risk_order = ["High", "Medium", "Low", "Unknown"]
    lines = [f"**{count}** contract audit(s) uploaded and analyzed{cat_label}{date_label}."]
    for risk in _risk_order:
        n = by_risk.get(risk, 0)
        if n:
            lines.append(f"  • {risk} risk: {n}")
    if filtered:
        lines.append("Files: " + _fmt_files(filtered))

    if not date_label:
        lines.append(f"\n_Total in system: {total_all} audits._")

    return "\n".join(lines)
