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


def _load_all_metadata() -> list[dict]:
    """Load all audits with their parsed contract metadata — cached per-call."""
    with session_scope() as s:
        rows = s.query(AuditRow).order_by(AuditRow.created_at.desc()).all()
        result = []
        for r in rows:
            meta = parse_contract_metadata(list(r.clauses or []))
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

def answer_meta_query(question: str) -> Optional[str]:
    """Answer a structured metadata question about contracts. Returns None if not handled."""
    q = question.strip().lower()
    contracts = _load_all_metadata()
    if not contracts:
        return "No contract audits found. Upload a contract to get started."

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
        lines = [f"The **{label} contract** is {_fmt_contract_line(top)}."]
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
        lines = [f"**{len(contracts)}** analyzed contracts:\n"]
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
    lines = [f"**{count}** contract audit(s) uploaded and analyzed{date_label}."]
    for risk in _risk_order:
        n = by_risk.get(risk, 0)
        if n:
            lines.append(f"  • {risk} risk: {n}")
    if filtered:
        lines.append("Files: " + _fmt_files(filtered))

    if not date_label:
        lines.append(f"\n_Total in system: {total_all} audits._")

    return "\n".join(lines)
