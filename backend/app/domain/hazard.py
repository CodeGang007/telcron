"""The hazard total (technical documentation 7.4). A pure function with exact answers.

The band a total falls in (Low, Medium, High) and the alert threshold are rows in
`scoring_bands` and `scoring_contexts`; they are read from the database, not coded here.
"""

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
    a verified citation is `insufficient_data`: it must not count as a zero (that would make
    an unknown product look safe), so it drops out of both sums.
    """
    scored = [s for s in scores if s.score is not None]
    weight_sum = sum((s.weight for s in scored), Decimal(0))
    if weight_sum == 0:
        return None
    total = sum((s.weight * s.score for s in scored), Decimal(0)) / weight_sum  # type: ignore[operator]
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
