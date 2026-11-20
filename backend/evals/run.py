"""Grade a hazard scorer against the evaluation set.

    uv run python -m evals.run                     # the configured scorer (AI_PROVIDER)
    uv run python -m evals.run --min-agreement 0.6 # exit 1 if band agreement falls below this

A dimension's score is put in a band (none, low, medium, high) and compared with the expected band.
Also reported: citation validity (every citation must point at offered evidence) and how often a
dimension with no evidence was nevertheless scored. Writes evals/last-run.json.
"""

import argparse
import asyncio
import json
import pathlib
import sys
from datetime import UTC, datetime

from app.modules.screening.scorer import DimensionSpec, EvidenceRef, get_scorer

HERE = pathlib.Path(__file__).parent
DIMENSIONS = [
    DimensionSpec("safety.regulatory", "Regulatory Flags", "Recalls, banned substances, violations"),
    DimensionSpec("safety.health_safety", "Health & Safety", "Injury, toxic materials, choking risk"),
    DimensionSpec("safety.customer_issues", "Customer Issues", "One-star rate, repeated complaints"),
    DimensionSpec("safety.fragility", "Fragility / Usability", "Breakage reports, design flaws"),
    DimensionSpec("safety.environmental", "Environmental Harm", "Non-recyclable materials, disposal hazards"),
    DimensionSpec("safety.regional", "Regional Constraints", "Voltage, import restrictions, regional bans"),
    DimensionSpec("safety.animal_harm", "Animal Harm", "Toxic to pets, dangerous baits"),
]


def band(score) -> str:
    if score is None:
        return "none"
    return "low" if score < 30 else "medium" if score < 60 else "high"


async def evaluate() -> dict:
    cases = json.loads((HERE / "cases.json").read_text())["cases"]
    scorer = get_scorer()
    graded = agreed = cites = valid_cites = 0
    rows = []
    for case in cases:
        refs = [EvidenceRef(f"{case['id']}-{i}", kind, text)
                for i, (kind, text) in enumerate(case["evidence"])]
        results = {r.code: r for r in await scorer.score(case["product"], DIMENSIONS, refs)}
        offered = {r.id for r in refs}
        for code, expected in case["expect"].items():
            got = band(results[code].score) if code in results else "none"
            graded += 1
            agreed += got == expected
            rows.append({"case": case["id"], "dimension": code, "expected": expected, "got": got,
                         "ok": got == expected})
        for r in results.values():
            cites += len(r.citations)
            valid_cites += sum(c in offered for c in r.citations)
    report = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "scorer": getattr(scorer, "model_code", "?"),
        "prompt_version": getattr(scorer, "prompt_version", "?"),
        "fallback_error": getattr(scorer, "error", None),
        "cases": len(cases), "graded": graded,
        "agreement": round(agreed / graded, 3) if graded else 0.0,
        "citation_validity": round(valid_cites / cites, 3) if cites else 1.0,
        "misses": [r for r in rows if not r["ok"]],
    }
    (HERE / "last-run.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-agreement", type=float, default=0.0)
    args = parser.parse_args()
    report = asyncio.run(evaluate())
    print(f"scorer {report['scorer']} ({report['prompt_version']}): "  # noqa: T201
          f"agreement {report['agreement']:.0%} on {report['graded']} graded dimensions, "
          f"citation validity {report['citation_validity']:.0%}")
    for miss in report["misses"]:
        print(f"  miss  {miss['case']:<18} {miss['dimension']:<24} "  # noqa: T201
              f"expected {miss['expected']:<6} got {miss['got']}")
    if report["agreement"] < args.min_agreement:
        print(f"FAIL: agreement below {args.min_agreement:.0%}")  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
