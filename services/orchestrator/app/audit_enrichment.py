"""Enrich audit findings with clause excerpts and regulatory corpus text."""

from __future__ import annotations

import re
from typing import Any, Optional

_EXCERPT_LEN = 480

_KEYWORDS = (
    "terminat",
    "notice",
    "liability",
    "encrypt",
    "data",
    "retention",
    "indemn",
    "liquidity",
    "basel",
)


def _excerpt(text: str, max_len: int = _EXCERPT_LEN) -> str:
    t = " ".join(text.split())
    if not t:
        return ""
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def _finding_haystack(finding: dict[str, Any]) -> str:
    return (
        str(finding.get("justification") or "")
        + " "
        + str(finding.get("recommendation") or "")
    ).lower()


def _score_clause(c: dict[str, Any], active: list[str]) -> int:
    text = str(c.get("text") or "").lower()
    section = str(c.get("section") or "").lower()
    return sum(1 for k in active if k in text or k in section)


def resolve_clause_for_finding(
    finding: dict[str, Any],
    clauses: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Pick the clause row that best matches a finding (id remap + keyword fallback)."""
    if not clauses:
        return None

    clause_by_id = {str(c.get("id")): c for c in clauses if c.get("id")}
    cid = str(finding.get("contract_clause_id") or "")
    hay = _finding_haystack(finding)
    active = [k for k in _KEYWORDS if k in hay]

    clause = clause_by_id.get(cid)
    if clause and str(clause.get("text") or "").strip():
        return clause

    # Remap synthetic clause_1 to best segmented clause
    if cid == "clause_1" or not clause or not str(clause.get("text") or "").strip():
        best: Optional[dict[str, Any]] = None
        best_score = 0
        for c in clauses:
            text = str(c.get("text") or "").strip()
            if not text:
                continue
            score = _score_clause(c, active) if active else 0
            if score > best_score:
                best_score = score
                best = c
        if best_score > 0 and best:
            return best
        if "terminat" in hay:
            for c in clauses:
                if c.get("clause_type") == "termination" or "terminat" in str(
                    c.get("section") or ""
                ).lower():
                    if str(c.get("text") or "").strip():
                        return c
        # Non-empty clauses excluding empty clause_1 stub
        non_empty = [c for c in clauses if str(c.get("text") or "").strip()]
        if len(non_empty) == 1:
            return non_empty[0]
        if cid == "clause_1" and non_empty:
            return non_empty[0]

    if clause and not str(clause.get("text") or "").strip():
        combined = "\n\n".join(
            str(c.get("text") or "") for c in clauses if str(c.get("text") or "").strip()
        )
        if combined:
            return {
                "id": cid or "combined",
                "section": clause.get("section") or "Contract body",
                "text": combined,
                "clause_type": clause.get("clause_type"),
                "page": clause.get("page"),
            }

    return clause if clause else None


def clause_section_label(clause: dict[str, Any], fallback_id: str = "") -> str:
    section = str(clause.get("section") or "").strip()
    page = clause.get("page")
    if section and page is not None:
        return f"{section} (p. {page})"
    if section:
        return section
    return fallback_id or "—"


def apply_finding_clause_fields(
    finding: dict[str, Any],
    clauses: list[dict[str, Any]],
) -> dict[str, Any]:
    """Remap clause id and attach clause_section / clause_excerpt for persistence."""
    out = dict(finding)
    resolved = resolve_clause_for_finding(out, clauses)
    if resolved:
        rid = str(resolved.get("id") or out.get("contract_clause_id") or "")
        if rid:
            out["contract_clause_id"] = rid
        text = str(resolved.get("text") or "")
        if text.strip():
            out["clause_section"] = clause_section_label(
                resolved, str(out.get("contract_clause_id") or "")
            )
            out["clause_excerpt"] = _excerpt(text)
            if resolved.get("clause_type"):
                out["clause_type"] = resolved.get("clause_type")
    return out


def _corpus_index(corpus: list[dict]) -> dict[tuple[str, str], dict]:
    idx: dict[tuple[str, str], dict] = {}
    for item in corpus:
        src = str(item.get("source") or "").strip()
        art = str(item.get("article") or "").strip()
        if src:
            idx[(src.lower(), art.lower())] = item
            idx[(src.lower(), "")] = item
    return idx


def _lookup_regulation(
    corpus: list[dict],
    source: Optional[str],
    article: Optional[str],
) -> Optional[dict]:
    if not source:
        return None
    idx = _corpus_index(corpus)
    src_key = source.strip().lower()
    art_key = (article or "").strip().lower()
    hit = idx.get((src_key, art_key))
    if hit:
        return hit
    for (s, a), item in idx.items():
        if src_key in s or s in src_key:
            if not art_key or not a or art_key in a or a in art_key:
                return item
    return None


def enrich_finding(
    finding: dict[str, Any],
    clause_by_id: dict[str, dict[str, Any]],
    corpus: list[dict],
    clauses: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    out = dict(finding)
    all_clauses = clauses or list(clause_by_id.values())
    if not out.get("clause_excerpt") or not out.get("clause_section"):
        resolved = resolve_clause_for_finding(out, all_clauses)
        if resolved:
            cid = str(out.get("contract_clause_id") or resolved.get("id") or "")
            if resolved.get("id"):
                out["contract_clause_id"] = str(resolved["id"])
            text = str(resolved.get("text") or "")
            if text.strip():
                out["clause_section"] = clause_section_label(resolved, cid)
                out["clause_excerpt"] = _excerpt(text)
                if resolved.get("clause_type"):
                    out["clause_type"] = resolved.get("clause_type")
    elif out.get("contract_clause_id"):
        cid = str(out["contract_clause_id"])
        clause = clause_by_id.get(cid)
        if clause and not out.get("clause_type"):
            out["clause_type"] = clause.get("clause_type")

    if not out.get("clause_section"):
        out["clause_section"] = str(out.get("contract_clause_id") or "—")

    reg = _lookup_regulation(
        corpus,
        finding.get("matched_regulatory_source"),
        finding.get("matched_regulatory_article"),
    )
    if reg:
        out["regulatory_title"] = reg.get("title")
        out["regulatory_excerpt"] = _excerpt(str(reg.get("text") or ""), 320)
    return out


def enrich_findings(
    findings: list[dict[str, Any]],
    clauses: list[dict[str, Any]],
    corpus: list[dict],
) -> list[dict[str, Any]]:
    clause_by_id = {str(c.get("id")): c for c in clauses if c.get("id")}
    return [enrich_finding(f, clause_by_id, corpus, clauses) for f in findings]


def _clean(value: Optional[str]) -> Optional[str]:
    """Reject values that look like prose / legal boilerplate rather than a header field."""
    if not value:
        return None
    v = value.strip()
    bad = ("now therefore", "agrees as", "witnesseth", "hereinafter", "whereas", "\n")
    for b in bad:
        if b in v.lower():
            return None
    if len(v) > 120:
        return None
    if v and v[0].islower():
        return None
    return v or None


def _parse_two_column_parties(block_text: str) -> tuple[dict, dict]:
    """Parse parties stored side-by-side on the same lines (two-column PDF table format).

    Example block:
      PARTY A — ENGAGING INSTITUTION PARTY B — SERVICE PROVIDER
      First National Bank Corp. ANZ Banking Group Limited
      14 Exchange Square, New York, NY 10005 833 Collins Street, Docklands VIC 3008, Australia
      Regulated by: OCC, Federal Reserve, FDIC Regulated by: APRA (ADI Licence BL0001), ASIC
      LEI: 213800RRJKXB7OX1YK43 ABN: 11 005 357 522 | LEI: HB7FFAZI0OMZ8PP8OE15
    """
    empty: dict[str, Optional[str]] = {
        "name": None, "address": None, "regulated_by": None, "lei": None, "abn": None
    }
    party_a: dict[str, Optional[str]] = dict(empty)
    party_b: dict[str, Optional[str]] = dict(empty)

    lines = [l.strip() for l in block_text.splitlines() if l.strip()]
    for line in lines:
        # Skip the PARTY A / PARTY B header line
        if re.search(r"PARTY\s+A", line, re.IGNORECASE) and re.search(
            r"INSTITUTION|PROVIDER|PARTY\s+B", line, re.IGNORECASE
        ):
            continue

        # ── Company names ─────────────────────────────────────────────────
        if party_a["name"] is None:
            # Split at the boundary between the two company names:
            # e.g. "First National Bank Corp. ANZ Banking Group Limited"
            #      → split after first entity ending (Corp., Limited, Ltd., Inc.)
            split_m = re.match(
                r"^(.+?(?:Corp\.?|Ltd\.?|Inc\.?))\s+([A-Z].+(?:Limited|Ltd\.?|Group|Corp\.?|Bank|Inc\.?))\s*$",
                line,
            )
            if split_m:
                party_a["name"] = split_m.group(1).strip()
                party_b["name"] = split_m.group(2).strip()
                continue
            # Single entity on this line
            if re.search(
                r"Corp\.?|Limited|Ltd\.?|Inc\.?|Group\b|Bank\b", line, re.IGNORECASE
            ) and len(line) <= 120:
                party_a["name"] = line
                continue

        # ── Addresses ─────────────────────────────────────────────────────
        if party_a["address"] is None and re.search(r"\d+\s+[A-Z][a-z]", line):
            # Split after a 5-digit US ZIP code followed by a space + digit (new address)
            addr_m = re.search(r"(.*?\b\d{5})\s+(\d+.*)", line)
            if addr_m:
                party_a["address"] = addr_m.group(1).strip()
                party_b["address"] = addr_m.group(2).strip()
            else:
                party_a["address"] = line
            continue

        # ── Regulated by ──────────────────────────────────────────────────
        if re.search(r"Regulated\s+by", line, re.IGNORECASE):
            # Two "Regulated by" clauses may appear on the same line separated by a space
            dual_m = re.search(
                r"Regulated\s+by[:\s]+(.+?)\s+Regulated\s+by[:\s]+(.+)",
                line, re.IGNORECASE,
            )
            if dual_m:
                party_a["regulated_by"] = dual_m.group(1).strip()
                party_b["regulated_by"] = dual_m.group(2).strip()
            else:
                single_m = re.search(r"Regulated\s+by[:\s]+(.+)", line, re.IGNORECASE)
                if single_m:
                    target = party_a if party_a["regulated_by"] is None else party_b
                    target["regulated_by"] = single_m.group(1).strip()
            continue

        # ── LEI / ABN ─────────────────────────────────────────────────────
        lei_hits = list(re.finditer(r"\bLEI[:\s]+([A-Z0-9]{18,20})", line, re.IGNORECASE))
        abn_hit = re.search(r"\bABN[:\s]+([\d\s]{9,14})", line, re.IGNORECASE)
        if lei_hits:
            if party_a["lei"] is None:
                party_a["lei"] = lei_hits[0].group(1)
            if len(lei_hits) >= 2 and party_b["lei"] is None:
                party_b["lei"] = lei_hits[1].group(1)
        if abn_hit and party_b["abn"] is None:
            party_b["abn"] = abn_hit.group(1).strip()

    return party_a, party_b


def _extract_party_block(combined: str, section_re: str) -> dict[str, Optional[str]]:
    """Single-column party block extraction (fallback for non-two-column formats)."""
    start_m = re.search(rf"(?:{section_re})", combined, re.IGNORECASE)
    if not start_m:
        return {"name": None, "address": None, "regulated_by": None, "lei": None, "abn": None}

    next_section = re.search(
        r"\n(?:PARTY\s+[AB]\b|ARTICLE\s+\d|SECTION\s+\d|\d+\.\s+[A-Z])",
        combined[start_m.end():],
        re.IGNORECASE,
    )
    block = combined[start_m.end(): start_m.end() + (next_section.start() if next_section else 2000)]
    lines = [l.strip() for l in block.splitlines() if l.strip()]

    name: Optional[str] = None
    for line in lines[:8]:
        if line.startswith(("-", "–", "*", "•")) or line.isupper():
            continue
        if re.search(
            r"Corp\.?|Limited|Ltd\.?|Inc\.?|Group\b|Bank\b|Agency|Authority|Services\b",
            line, re.IGNORECASE,
        ) and len(line) <= 100:
            name = line
            break

    address: Optional[str] = None
    for line in lines:
        if re.search(r"\d+\s+[A-Z][a-z]|\b(?:Street|St\.|Avenue|Ave|Road|Rd|Square)\b", line, re.IGNORECASE):
            address = line if len(line) <= 120 else None
            break

    regulated_by: Optional[str] = None
    for line in lines:
        m = re.search(r"Regulated\s+by[:\s]+(.+)", line, re.IGNORECASE)
        if m:
            regulated_by = m.group(1).strip()
            break

    lei: Optional[str] = None
    for line in lines:
        m = re.search(r"\bLEI[:\s]+([A-Z0-9]{18,20})", line, re.IGNORECASE)
        if m:
            lei = m.group(1).strip()
            break

    abn: Optional[str] = None
    for line in lines:
        m = re.search(r"\bABN[:\s]+([\d\s]{9,14})", line, re.IGNORECASE)
        if m:
            abn = m.group(1).strip()
            break

    return {"name": name, "address": address, "regulated_by": regulated_by, "lei": lei, "abn": abn}


# Cover-page label synonyms → canonical field. Longest / most specific labels
# MUST come first so e.g. "Contract Portfolio ID" matches before "Contract ID".
_KV_LABELS: list[tuple[str, list[str]]] = [
    ("contract_number", ["Contract Portfolio ID", "Contract ID", "Contract Number", "Contract No."]),
    ("effective_date", ["Effective Date", "Commencement Date", "Start Date"]),
    ("expiry_date", ["Expiry Date", "Expiration Date", "Review Date", "End Date"]),
    ("contract_value", ["Total Portfolio Value", "Total Contract Value", "Contract Value", "Contract Amount"]),
    ("contract_manager", ["Contract Manager", "Portfolio Manager", "Account Manager"]),
    ("payment_terms", ["Payment Terms"]),
    ("status", ["Status"]),
    ("jurisdiction", ["Jurisdiction", "Governing Law"]),
]

# Column-header words that get mis-captured when a label also names a table column.
_BAD_VALUES = {
    "supplier", "category", "value", "value (usd)", "contracts", "status", "risk",
    "compliance", "amount", "amount (usd)", "frequency", "due date", "period",
    "penalty trigger", "target", "metric", "—", "-", "n/a",
}


def _scan_kv_table(text: str) -> dict[str, str]:
    """Parse a cover-page key/value table.

    Handles single-column ("Label  Value") and two-column ("Label1 Value1 Label2
    Value2") rows by locating every known label on a line and taking each value
    as the text between consecutive labels.
    """
    found: dict[str, str] = {}
    label_to_field: dict[str, str] = {}
    alts: list[str] = []
    for field, labels in _KV_LABELS:
        for lab in labels:
            label_to_field[lab.lower()] = field
            alts.append(re.escape(lab))
    label_re = re.compile(r"(?<![A-Za-z])(" + "|".join(alts) + r")(?![A-Za-z])", re.IGNORECASE)

    for line in text.splitlines():
        matches = list(label_re.finditer(line))
        if not matches:
            continue
        for i, m in enumerate(matches):
            field = label_to_field.get(m.group(1).lower())
            if not field or field in found:
                continue
            end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
            value = line[m.end():end]
            value = re.sub(r"^[\s:|\-–—]+", "", value).strip()
            value = value.split("  ")[0].strip()  # drop trailing column if collapsed
            if not value or value.lower() in _BAD_VALUES:
                continue
            if len(value) > 80:
                value = value[:80].rstrip()
            found[field] = value
    return found


def parse_contract_metadata(clauses: list[dict[str, Any]]) -> dict[str, Optional[str]]:
    """Extract header fields from contract PDFs.

    Strategy:
      1. Parse the cover-page key/value table (single- or two-column) for the
         canonical fields — this is where clean labelled data lives.
      2. Fall back to body-derived patterns (pipe-separated header line, date
         range, "USD …" value, "Governed by …", two-column party block) for any
         field still missing.
    """
    combined = "\n".join(str(c.get("text") or "") for c in clauses[:12])
    if not combined:
        combined = "\n".join(str(c.get("text") or "") for c in clauses)

    # 1) Cover-table parse takes priority. Only scan the dedicated Document
    #    Header clause — running the KV scanner over body prose / table headers
    #    produces false positives (e.g. "Status" → "Risk Compliance").
    header_text = next(
        (str(c.get("text") or "") for c in clauses if "header" in str(c.get("section") or "").lower()),
        "",
    )
    kv = _scan_kv_table(header_text) if header_text else {}

    contract_number = kv.get("contract_number")
    effective_date = kv.get("effective_date")
    expiry_date = kv.get("expiry_date")
    contract_value = kv.get("contract_value")
    payment_terms = kv.get("payment_terms")
    contract_manager = kv.get("contract_manager")
    status = kv.get("status")
    jurisdiction = kv.get("jurisdiction")

    # ── Contract number (body fallback) ───────────────────────────────────
    # A real contract id always contains a digit — this rejects "Supplier" etc.
    if not contract_number or not re.search(r"\d", contract_number):
        contract_number = None
        m = re.search(r"\bContract\s+([A-Z]{2,8}-\d{4}-[A-Z0-9]{2,12})\b", combined, re.IGNORECASE)
        if m:
            contract_number = m.group(1)
        if not contract_number:
            m = re.search(
                r"Contract\s+(?:ID|No\.?|Number)\s*[:\|]?\s*([A-Z]{2,}-[A-Z0-9\-]{3,30})",
                combined, re.IGNORECASE,
            )
            if m:
                contract_number = m.group(1).strip()

    # ── Date range (body fallback) ────────────────────────────────────────
    MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    if not effective_date or not expiry_date:
        date_range_m = re.search(
            rf"({MONTHS}\s+\d{{1,2}},?\s+\d{{4}})\s*[\u2013\u2014\u2015\ufffd\-]+\s*({MONTHS}\s+\d{{1,2}},?\s+\d{{4}})",
            combined, re.IGNORECASE,
        )
        if date_range_m:
            effective_date = effective_date or date_range_m.group(1).strip()
            expiry_date = expiry_date or date_range_m.group(2).strip()

    # ── Contract value (body fallback) ────────────────────────────────────
    if not contract_value:
        m = re.search(r"TOTAL\s+(?:PORTFOLIO|CONTRACT)\s+VALUE\s*\$?([\d,]+)", combined, re.IGNORECASE)
        if m:
            contract_value = f"USD ${m.group(1)}"
    if not contract_value:
        m = re.search(r"\bUSD\s+\$?([\d,]+(?:\.\d+)?)", combined, re.IGNORECASE)
        if m:
            contract_value = f"USD {m.group(1)}"

    # ── Jurisdiction / Governing law (body fallback) ──────────────────────
    if not jurisdiction:
        m = re.search(r"Governed\s+by\s+([\w\s,]+?)\s+(?:law|laws)\b", combined, re.IGNORECASE)
        if m:
            jurisdiction = m.group(1).strip()

    # ── Payment terms (body fallback) — derive from distinct "Net NN" tags ──
    if not payment_terms:
        nets = sorted({f"Net {n}" for n in re.findall(r"\bNet\s+(\d{1,3})\b", combined)},
                      key=lambda s: int(s.split()[1]))
        if nets:
            payment_terms = " / ".join(nets)

    # ── Parties ───────────────────────────────────────────────────────────
    two_col_m = re.search(r"(PARTY\s+A[^\n]*PARTY\s+B[^\n]*\n.*?)(?:\n\n|\Z)", combined, re.IGNORECASE | re.DOTALL)
    if two_col_m:
        party_a_info, party_b_info = _parse_two_column_parties(two_col_m.group(0))
    else:
        party_a_info = _extract_party_block(combined, r"PARTY\s*A\b|ENGAGING\s+INSTITUTION")
        party_b_info = _extract_party_block(combined, r"PARTY\s*B\b|SERVICE\s+PROVIDER")

    return {
        "contract_number": contract_number,
        "effective_date": effective_date,
        "expiry_date": expiry_date,
        "jurisdiction": jurisdiction,
        "contract_value": contract_value,
        "payment_terms": payment_terms,
        "contract_manager": contract_manager,
        "status": status,
        # Party A
        "party_a": party_a_info["name"],
        "party_a_address": party_a_info["address"],
        "party_a_regulated_by": party_a_info["regulated_by"],
        "party_a_lei": party_a_info["lei"],
        # Party B
        "party_b": party_b_info["name"],
        "party_b_address": party_b_info["address"],
        "party_b_regulated_by": party_b_info["regulated_by"],
        "party_b_lei": party_b_info["lei"],
        "party_b_abn": party_b_info["abn"],
        # kept for backward compat
        "term": None,
        "governing_law": jurisdiction,
    }


def parties_from_metadata(meta: dict[str, Optional[str]]) -> list[str]:
    parties: list[str] = []
    for key in ("party_a", "party_b"):
        v = meta.get(key)
        if v and v.strip() and v.strip() not in parties:
            parties.append(v.strip())
    return parties
