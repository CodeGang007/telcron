"""Rules with exact answers: hazard formula, passport combination, coin fraud rules."""

from decimal import Decimal as D

from app.domain import passport
from app.domain.coins import capped_amount, is_burst, streak_multiplier
from app.domain.hazard import DimensionScore, label_for, total_score

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
    assert label_for(None) is None


def test_band_edges():
    assert label_for(D("29.99")) == "low"
    assert label_for(D("30")) == "medium"
    assert label_for(D("59.99")) == "medium"
    assert label_for(D("60")) == "high"


def test_confirmed_recall_always_reads_recalled():
    result = passport.build("confirmed_match", ["valid"], D("5"), "low")
    assert result.status_badge == "recalled"
    assert result.recall_component == 0


def test_high_hazard_is_blocked_and_low_with_valid_cert_is_verified():
    assert passport.build("no_match", ["valid"], D("75"), "high").status_badge == "blocked"
    assert passport.build("no_match", ["valid"], D("10"), "low").status_badge == "verified"
    assert passport.build("no_match", [], D("10"), "low").status_badge == "unverified"


def test_no_hazard_total_means_no_trust_score():
    result = passport.build("no_match", [], None, None)
    assert result.trust_score is None and result.tier == 4


def test_daily_cap_clips_the_award():
    assert capped_amount(25, 490, True) == 10
    assert capped_amount(25, 500, True) == 0
    assert capped_amount(100, 500, False) == 100


def test_burst_and_streak():
    assert not is_burst(19) and is_burst(20)
    assert streak_multiplier(7) == 1 and streak_multiplier(8) == 2
