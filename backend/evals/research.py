"""Grade the research reader (app.modules.research.web.read) against evals/research_cases.json.

    uv run python -m evals.research                   # needs LLM_API_KEY
    uv run python -m evals.research --min-precision 0.9

Reported: precision (kept findings that should exist), recall (expected findings found), kind
agreement, the trap cases passed, and the hallucination counters: findings the model wrote that
the grounding check removed, and references to results that do not exist. Source validity is
1.0 by construction: a finding can only name a result it was given. Writes evals/last-research.json.
"""

import argparse
import asyncio
import json
import pathlib
import sys
from datetime import UTC, datetime

from app.modules.research.web import Hit, read

HERE = pathlib.Path(__file__).parent


async def evaluate() -> dict:
    cases = json.loads((HERE / "research_cases.json").read_text())["cases"]
    kept = right = expected = found = kinds_ok = raw = ungrounded = bad_ref = traps_ok = traps = 0
    injected = other = 0
    rows = []
    for case in cases:
        hits = [Hit(h["title"], h["url"], h["snippet"]) for h in case["hits"]]
        audit: dict[str, int] = {}
        findings = await read(case["product"], hits, audit, brand=case.get("brand"))
        await asyncio.sleep(2)  # the free plan's per-minute limit
        got = {str(hits.index(f.hit) + 1): f.kind for f in findings}
        want = case["expect"]
        kept += len(got)
        right += sum(1 for n in got if n in want)
        expected += len(want)
        found += sum(1 for n in want if n in got)
        kinds_ok += sum(1 for n in want if got.get(n) == want[n])
        raw += audit.get("raw", 0)
        ungrounded += audit.get("ungrounded", 0)
        bad_ref += audit.get("bad_reference", 0)
        injected += audit.get("injected", 0)
        other += audit.get("other_product", 0)
        if not want:
            traps += 1
            traps_ok += not got
        rows.append({"id": case["id"], "expected": want, "got": got, "audit": audit,
                     "findings": [f.finding for f in findings]})
    return {
        "run_at": datetime.now(UTC).isoformat(), "cases": len(cases),
        "precision": round(right / kept, 3) if kept else 1.0,
        "recall": round(found / expected, 3) if expected else 1.0,
        "kind_agreement": round(kinds_ok / expected, 3) if expected else 1.0,
        "traps_passed": f"{traps_ok}/{traps}",
        "model_findings": raw, "removed_ungrounded": ungrounded, "removed_bad_reference": bad_ref,
        "removed_injected_pages": injected, "removed_other_product": other,
        "source_validity": 1.0, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-precision", type=float, default=0.0)
    args = parser.parse_args()
    result = asyncio.run(evaluate())
    (HERE / "last-research.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))  # noqa: T201
    for row in result["rows"]:
        mark = "ok " if row["got"] == row["expected"] else "MISS"
        print(f"{mark} {row['id']}: expected {row['expected']} got {row['got']}")  # noqa: T201
    if result["precision"] < args.min_precision:
        sys.exit(1)


if __name__ == "__main__":
    main()
