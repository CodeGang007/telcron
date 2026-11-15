"""How recall, certification and hazard combine into a passport.

The vocabulary is the designed schema's: tier 0 unidentified, 1 identified, 2 verified; badge
verified | recalled | certification_issue | needs_information. The database enforces the hard
rules (a match forces `recalled`; below tier 2 the badge is `needs_information`; tier 2 needs a
trust score).

The NUMBERS are PROVISIONAL — formula_version `provisional-0`. Neither the v2 architecture
document nor the schema design (open question Q3) defines the trust-score formula or badge
bands. ADR-004 records this placeholder. Do not tune these numbers without that decision.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

FORMULA_VERSION = "provisional-0"
RECALL_WEIGHT, CERT_WEIGHT, HAZARD_WEIGHT = Decimal("0.4"), Decimal("0.2"), Decimal("0.4")

RECALL_COMPONENT = {"no_match_found": Decimal(100), "near_match": Decimal(40),
                    "match": Decimal(0)}
BAD_CERTIFICATE = ("expired", "revoked")


@dataclass(frozen=True)
class PassportResult:
    tier: int
    status_badge: str
    trust_score: Decimal | None
    recall_component: Decimal | None
    certification_component: Decimal | None
    hazard_component: Decimal | None


def certification_component(statuses: list[str]) -> Decimal:
    if any(s in BAD_CERTIFICATE for s in statuses):
        return Decimal(0)
    if "valid" in statuses:
        return Decimal(100) if all(s == "valid" for s in statuses) else Decimal(85)
    return Decimal(70)  # nothing known either way; never a negative finding


def unidentified() -> PassportResult:
    """The product's identity is not established: nothing can be claimed about it."""
    return PassportResult(0, "needs_information", None, None, None, None)


def build(recall_verdict: str, cert_statuses: list[str],
          hazard_total: Decimal | None) -> PassportResult:
    if recall_verdict == "insufficient_information":
        return PassportResult(1, "needs_information", None, None, None, None)
    recall = RECALL_COMPONENT[recall_verdict]
    cert = certification_component(cert_statuses)
    hazard = None if hazard_total is None else Decimal(100) - hazard_total
    # Tier 2 requires a trust score, so a missing hazard component drops out of the mean
    # instead of counting as zero or as a hundred.
    parts = [(recall, RECALL_WEIGHT), (cert, CERT_WEIGHT)]
    if hazard is not None:
        parts.append((hazard, HAZARD_WEIGHT))
    trust = (sum(v * w for v, w in parts) / sum(w for _, w in parts)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)

    if recall_verdict == "match":
        badge = "recalled"
    elif recall_verdict == "near_match":
        badge = "needs_information"  # a possible recall is not a recall, and not a clean bill
    elif any(s in BAD_CERTIFICATE for s in cert_statuses):
        badge = "certification_issue"
    else:
        badge = "verified"
    return PassportResult(2, badge, trust, recall, cert, hazard)
