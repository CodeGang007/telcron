"""Rules with exact answers: the hazard total and the passport combination."""

from decimal import Decimal as D

from app.domain import passport
from app.domain.hazard import DimensionScore, total_score

WEIGHTS = ["3.0", "2.5", "1.5", "1.5", "1.0", "1.0", "0.5"]


def scores(values):
    return [DimensionScore(str(i), D(w), None if v is None else D(v))
            for i, (w, v) in enumerate(zip(WEIGHTS, values, strict=True))]


def test_total_divides_by_eleven_when_all_seven_are_scored():
    # (3*100 + 2.5*80 + 1.5*40 + 1.5*20 + 1*0 + 1*10 + 0.5*60) / 11 = 630 / 11
    assert total_score(scores([100, 80, 40, 20, 0, 10, 60])) == D("57.27")


def test_all_equal_scores_give_that_score():
    assert total_score(scores([50] * 7)) == D("50.00")


def test_insufficient_dimension_is_excluded_not_counted_as_zero():
    # Only regulatory (3.0) and health (2.5) scored: (300 + 125) / 5.5
    assert total_score(scores([100, 50, None, None, None, None, None])) == D("77.27")


def test_nothing_scored_gives_no_total():
    assert total_score(scores([None] * 7)) is None


def test_a_match_reads_recalled_and_still_has_a_trust_score():
    result = passport.build("match", ["valid"], None)
    assert (result.tier, result.status_badge) == (2, "recalled")
    assert result.recall_component == 0
    assert result.trust_score is not None  # the schema requires one at tier 2


def test_a_near_match_is_neither_recalled_nor_verified():
    assert passport.build("near_match", ["valid"], D("5")).status_badge == "needs_information"


def test_a_bad_certificate_is_a_certification_issue():
    for status in ("expired", "revoked"):
        result = passport.build("no_match_found", ["valid", status], D("5"))
        assert result.status_badge == "certification_issue"
        assert result.certification_component == 0


def test_no_recall_and_nothing_wrong_is_verified():
    result = passport.build("no_match_found", ["valid"], D("10"))
    assert (result.tier, result.status_badge) == (2, "verified")
    assert result.hazard_component == D("90")
    assert result.trust_score == D("96.00")  # 0.4*100 + 0.2*100 + 0.4*90


def test_a_missing_hazard_total_drops_out_of_the_trust_score():
    assert passport.build("no_match_found", ["valid"], None).trust_score == D("100.00")


def test_below_tier_two_the_badge_is_needs_information_with_no_score():
    for result in (passport.build("insufficient_information", [], None), passport.unidentified()):
        assert result.tier < 2 and result.status_badge == "needs_information"
        assert result.trust_score is None


def test_certification_component():
    assert passport.certification_component([]) == 70
    assert passport.certification_component(["not_checked"]) == 70
    assert passport.certification_component(["valid", "not_checked"]) == 85
    assert passport.certification_component(["valid"]) == 100
    assert passport.certification_component(["lookup_failed", "expired"]) == 0
