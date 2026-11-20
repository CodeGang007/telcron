"""The scorer boundary. A scorer is the ONLY thing that produces hazard scores; it is replaced
wholesale in tests. `StubScorer` is a keyword heuristic for local development — it is not AI and
it is used when no model is configured, or when the model cannot answer (see llm.py)."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class EvidenceRef:
    id: str
    kind: str  # an evidence_kind: recall | certification_check | review | hazard_flag | ...
    text: str


@dataclass(frozen=True)
class DimensionSpec:
    code: str
    name: str
    description: str | None


@dataclass
class DimensionResult:
    code: str
    score: Decimal | None
    justification: str
    citations: list[str] = field(default_factory=list)


class Scorer(Protocol):
    model_code: str
    prompt_version: str

    async def score(self, product_text: str, dimensions: list[DimensionSpec],
                    evidence: list[EvidenceRef]) -> list[DimensionResult]: ...


KEYWORDS: dict[str, tuple[str, ...]] = {
    "safety.regulatory": ("recall", "banned", "non-compliant", "violation", "counterfeit"),
    "safety.health_safety": ("injur", "burn", "fire", "shock", "toxic", "chok", "cut", "overheat",
                      "smoke", "explod", "laceration"),
    "safety.customer_issues": ("broke", "stopped working", "refund", "defective", "terrible",
                               "faulty"),
    "safety.fragility": ("crack", "fragile", "flimsy", "snapped", "leak", "loose"),
    "safety.environmental": ("non-recyclable", "landfill", "pollut", "disposal hazard"),
    "safety.regional": ("voltage", "import restriction", "not approved in", "110v", "220v"),
    "safety.animal_harm": ("toxic to pets", "pet", "bait", "poison"),
}
# Which evidence kinds a dimension may be scored from.
SOURCES: dict[str, tuple[str, ...]] = {
    "safety.regulatory": ("recall", "certification_check", "hazard_flag"),
}
DEFAULT_SOURCES = ("review", "hazard_flag", "recall")


class StubScorer:
    model_code = "stub-heuristic-0"
    prompt_version = "n/a"

    async def score(self, product_text: str, dimensions: list[DimensionSpec],
                    evidence: list[EvidenceRef]) -> list[DimensionResult]:
        out: list[DimensionResult] = []
        for dim in dimensions:
            pool = [ev for ev in evidence if ev.kind in SOURCES.get(dim.code, DEFAULT_SOURCES)]
            if not pool:
                out.append(DimensionResult(dim.code, None, "No evidence available."))
                continue
            words = KEYWORDS.get(dim.code, ())
            hits = [ev for ev in pool if any(w in ev.text.lower() for w in words)]
            if dim.code == "safety.regulatory":
                hits = hits or [ev for ev in pool if ev.kind == "recall"]
            if hits:
                weight = sum(40 if ev.kind in ("recall", "hazard_flag") else 20 for ev in hits)
                out.append(DimensionResult(
                    dim.code, Decimal(min(100, weight)),
                    f"{len(hits)} of {len(pool)} evidence items mention this hazard.",
                    [ev.id for ev in hits[:5]]))
            else:
                out.append(DimensionResult(
                    dim.code, Decimal(0),
                    f"No mention in {len(pool)} evidence items.", [ev.id for ev in pool[:3]]))
        return out


def get_scorer() -> Scorer:
    settings = get_settings()
    if settings.ai_provider == "llm" and settings.llm_api_key:
        from .llm import FallbackScorer, LlmScorer
        return FallbackScorer(LlmScorer())
    return StubScorer()
