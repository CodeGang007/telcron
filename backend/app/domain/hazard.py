"""Hazard scoring rules with exact answers (technical documentation 7.4). Pure functions."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class DimensionScore:
    code: str
    weight: Decimal
    score: Decimal | None  # None = insufficient evidence; excluded from the total


def total_score(scores: list[DimensionScore]) -> Decimal | None:
    """Sum of (weight x score) divided by the sum of the weights that were scored.

    With all seven dimensions scored the divisor is 11, as documented. A dimension without
    a verified citation is `insufficient`: it must not count as a zero (that would make an
    unknown product look safe), so it drops out of both sums.
    """
    scored = [s for s in scores if s.score is not None]
    weight_sum = sum((s.weight for s in scored), Decimal(0))
    if weight_sum == 0:
        return None
    total = sum((s.weight * s.score for s in scored), Decimal(0)) / weight_sum  # type: ignore[operator]
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def label_for(total: Decimal | None) -> str | None:
    """0-29 low (approved), 30-59 medium (review queue), 60+ high (blocked, alert)."""
    if total is None:
        return None
    if total < 30:
        return "low"
    if total < 60:
        return "medium"
    return "high"
