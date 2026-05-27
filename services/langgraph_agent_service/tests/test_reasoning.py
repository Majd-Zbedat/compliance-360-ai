from __future__ import annotations

from services.langgraph_agent_service.app.reasoning import (
    ReasoningInput,
    _rule_based,
)


def test_rule_flags_no_encryption_as_high():
    out = _rule_based(
        ReasoningInput(
            clause_id="c1",
            clause_text=(
                "The Provider shall store personal data without encryption "
                "and shall not implement cryptographic safeguards."
            ),
            clause_type="data_processing",
            matches=[
                {
                    "id": "GDPR-32",
                    "source": "GDPR",
                    "article": "Art. 32",
                    "score": 0.7,
                    "text": "Implement appropriate security measures including encryption.",
                }
            ],
        )
    )
    assert out.verdict == "non_compliant"
    assert out.risk == "High"
    assert "GDPR" in out.justification


def test_rule_compliant_when_aligned():
    out = _rule_based(
        ReasoningInput(
            clause_id="c2",
            clause_text="Either party may terminate this Agreement upon thirty (30) days written notice.",
            clause_type="termination",
            matches=[
                {
                    "id": "LL-EMP-1",
                    "source": "LocalLaw",
                    "article": "Employment Contracts - 6",
                    "score": 0.6,
                    "text": "Termination notice no less than 30 days.",
                }
            ],
        )
    )
    assert out.verdict == "compliant"
    assert out.risk == "Low"


def test_rule_ambiguous_when_no_matches():
    out = _rule_based(
        ReasoningInput(
            clause_id="c3",
            clause_text="The header is the property of Acme.",
            clause_type="other",
            matches=[],
        )
    )
    assert out.verdict == "ambiguous"
