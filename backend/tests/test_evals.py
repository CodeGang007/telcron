"""The hazard-scoring regression baseline (WO-057) is whole and well-formed. Pure: no model is
called; `python -m evals.run` grades a scorer against it."""

import json

from evals.run import DIMENSIONS, HERE

BANDS = {"none", "low", "medium", "high"}
KINDS = {"recall", "review", "certification_check"}


def test_the_baseline_has_twenty_well_formed_cases():
    data = json.loads((HERE / "cases.json").read_text())
    cases = data["cases"]
    assert len(cases) == 20 and "regression baseline" in data["about"].lower()
    assert len({c["id"] for c in cases}) == 20
    codes = {d.code for d in DIMENSIONS}
    for case in cases:
        assert case["product"] and case["expect"], case["id"]
        assert set(case["expect"]) <= codes, case["id"]
        assert set(case["expect"].values()) <= BANDS, case["id"]
        assert all(kind in KINDS and text for kind, text in case["evidence"]), case["id"]


def test_every_case_without_a_recall_expects_no_regulatory_risk_it_cannot_cite():
    """No recall cited means the scorer must not invent one: such a case never expects a
    medium or high regulatory band."""
    for case in json.loads((HERE / "cases.json").read_text())["cases"]:
        if not any(kind == "recall" for kind, _ in case["evidence"]):
            assert case["expect"].get("safety.regulatory", "none") in {"none", "low"}, case["id"]
