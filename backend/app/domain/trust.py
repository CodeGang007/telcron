"""How a member's trust score moves (technical documentation 8.4).

The document says confirmed contributions raise the score and rejected ones lower it; it does not
say by how much. These amounts are PROVISIONAL (ADR-004) and live here so there is one place to
change them. The score stays between 0 and 100, and every change is a trust_score_events row.
"""

from decimal import Decimal

DELTAS: dict[str, Decimal] = {
    "hazard_flag_confirmed": Decimal("2"),
    "hazard_flag_rejected": Decimal("-1"),
    "fact_report_accepted": Decimal("1"),
    "fact_report_rejected": Decimal("-0.5"),
}


def apply(current: Decimal, reason: str) -> tuple[Decimal, Decimal]:
    """Returns (score after, the change actually made) for a reason code."""
    after = max(Decimal(0), min(Decimal(100), current + DELTAS[reason]))
    return after, after - current
