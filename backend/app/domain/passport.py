"""How recall, certification and hazard combine into a passport.

PROVISIONAL — formula_version `provisional-0`. The v2 architecture document does not define
this combination (technical documentation 7.5, open point 2). ADR-004 records the placeholder
and that Telcron must agree the real formula. Do not tune these numbers without that decision.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

FORMULA_VERSION = "provisional-0"
RECALL_WEIGHT, CERT_WEIGHT, HAZARD_WEIGHT = Decimal("0.4"), Decimal("0.2"), Decimal("0.4")

RECALL_COMPONENT = {"no_match": Decimal(100), "possible_match": Decimal(40),
                    "confirmed_match": Decimal(0)}


@dataclass(frozen=True)
class PassportResult:
    recall_component: Decimal
    certification_component: Decimal
    hazard_component: Decimal | None
    trust_score: Decimal | None
    tier: int
    status_badge: str


def certification_component(statuses: list[str]) -> Decimal:
    if "valid" in statuses:
        return Decimal(100)
    if any(s in ("revoked", "suspended", "expired") for s in statuses):
        return Decimal(0)
    return Decimal(50)  # nothing known either way


def build(recall_verdict: str, cert_statuses: list[str], hazard_total: Decimal | None,
          hazard_label: str | None) -> PassportResult:
    recall = RECALL_COMPONENT[recall_verdict]
    cert = certification_component(cert_statuses)
    hazard = None if hazard_total is None else Decimal(100) - hazard_total
    trust = None
    if hazard is not None:
        trust = (recall * RECALL_WEIGHT + cert * CERT_WEIGHT + hazard * HAZARD_WEIGHT).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)

    if recall_verdict == "confirmed_match":
        badge = "recalled"
    elif hazard_label == "high":
        badge = "blocked"
    elif hazard_label == "medium" or recall_verdict == "possible_match":
        badge = "caution"
    elif hazard_label == "low" and "valid" in cert_statuses:
        badge = "verified"
    else:
        badge = "unverified"

    if trust is None:
        tier = 4
    elif trust >= 80:
        tier = 1
    elif trust >= 60:
        tier = 2
    elif trust >= 40:
        tier = 3
    else:
        tier = 4
    return PassportResult(recall, cert, hazard, trust, tier, badge)
