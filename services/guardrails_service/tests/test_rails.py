from __future__ import annotations

from services.guardrails_service.app.rails import check_input, check_output


def test_input_rejects_spam():
    r = check_input("buy now! Limited time offer! Click here!")
    assert r["passed"] is False
    assert "offtopic" in " ".join(r["matched_rules"])


def test_input_accepts_contract():
    sample = (
        "This Services Agreement is entered into between Acme Corp (the Provider) "
        "and Beta Ltd (the Customer). The parties hereby agree to the following clauses, "
        "including liability, termination, and governing law obligations of each party."
    )
    r = check_input(sample)
    assert r["passed"] is True


def test_output_rewrites_imperative():
    advice = "You must comply with Article 6 of the GDPR. This is illegal."
    r = check_output(advice)
    assert r["safe_text"] is not None
    assert "you must" not in r["safe_text"].lower()
    assert "this is illegal" not in r["safe_text"].lower()
    assert r["matched_rules"]


def test_output_passes_neutral_analysis():
    neutral = "Clause 3 may be inconsistent with GDPR Art. 32 because it omits encryption-at-rest."
    r = check_output(neutral)
    assert r["passed"] is True
    assert r["matched_rules"] == []
