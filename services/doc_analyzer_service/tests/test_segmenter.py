from __future__ import annotations

from services.doc_analyzer_service.app.segmenter import segment


SAMPLE = """
SERVICES AGREEMENT

1. Definitions
"Agreement" means this services agreement and all schedules.
"Personal Data" has the meaning given in Article 4 of the GDPR.

2. Data Processing
The Provider shall process personal data on behalf of the Customer strictly to provide the services.
The Provider shall implement appropriate technical and organisational measures consistent with Article 32 of the GDPR including encryption at rest.

3. Liability
The Provider's total aggregate liability under this Agreement shall be limited to fees paid in the preceding twelve months. The Provider shall not be liable for any indirect or consequential damages.

4. Termination
Either party may terminate this Agreement upon thirty (30) days written notice.

5. Governing Law
This Agreement shall be governed by the laws of the State.
""".strip()


def test_segmenter_finds_named_sections():
    clauses = segment(SAMPLE, contract_id="contract-1", min_chars=20)
    types = {c["clause_type"] for c in clauses}
    sections = [c["section"] for c in clauses]
    assert any("Data Processing" in s for s in sections)
    assert any("Liability" in s for s in sections)
    assert "data_processing" in types
    assert "liability" in types
    assert "governing_law" in types
    assert "termination" in types
