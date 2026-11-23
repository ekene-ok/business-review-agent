"""Tests for the guardrails: data checks, the number verifier and the writer fallback."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bra.data import generate, inject, Scenario
from bra.agent import run
from bra.writer import LLMWriter
from bra.verify import verify


def test_clean_week_passes_and_verifies():
    review = run(generate(seed=1))
    assert review.verified and not review.provisional


def test_missing_rows_make_review_provisional():
    df = inject(generate(seed=2), Scenario("missing_rows", "SMB", "EMEA"))
    review = run(df)
    assert review.provisional
    assert any(i["check"] == "missing_rows" and i["segment"] == "SMB" for i in review.context.issues)


def test_duplicate_rows_detected_and_not_double_counted():
    base = generate(seed=3)
    df = inject(base, Scenario("duplicate_rows", "Enterprise", "North America"))
    review = run(df)
    assert any(i["check"] == "duplicate_rows" for i in review.context.issues)
    assert review.context.headline["latest"].tolist() == run(base).context.headline["latest"].tolist()


def test_large_drop_is_detected_in_the_right_cell():
    df = inject(generate(seed=4), Scenario("drop", "Mid-Market", "EMEA", "new_arr", -0.45))
    hits = [(a.segment, a.region, a.metric) for a in run(df).context.anomalies]
    assert ("Mid-Market", "EMEA", "new_arr") in hits


def test_verifier_rejects_invented_numbers():
    ok, unknown = verify("Revenue grew 12.5% to $4.20M", {"$4.20M"})
    assert not ok and unknown == ["12.5%"]


def test_llm_output_with_invented_number_falls_back_to_template():
    def fake_transport(payload):  # a "model" that adds a number not in the data
        return {"choices": [{"message": {"content": "Great week: revenue up 99.9% overall."}}]}
    review = run(generate(seed=5), writer=LLMWriter(transport=fake_transport))
    assert review.writer_used == "template" and review.verified


def test_llm_output_that_keeps_numbers_is_accepted():
    from bra.writer import TemplateWriter
    def faithful(payload):  # a "model" that only rewords, leaving every number intact
        text = payload["messages"][0]["content"].split("\n\n", 1)[1]
        return {"choices": [{"message": {"content": text.replace("Headline numbers", "Key numbers")}}]}
    review = run(generate(seed=6), writer=LLMWriter(transport=faithful))
    assert review.writer_used == "llm" and review.verified


def test_failing_service_falls_back_to_template():
    def broken(payload):
        raise TimeoutError("service unavailable")
    review = run(generate(seed=7), writer=LLMWriter(transport=broken))
    assert review.writer_used == "template" and review.verified
