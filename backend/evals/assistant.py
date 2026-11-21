"""Grade the product assistant (app.modules.assistant.chat.respond) on evals/assistant_cases.json.

    uv run python -m evals.assistant          # needs LLM_API_KEY

Reported: answered when it should (with a citation and the key words), declined when it should
(unknown, off-topic, unsafe, injected), and the count of answers the code checks replaced.
Writes evals/last-assistant.json.
"""

import asyncio
import json
import pathlib
from datetime import UTC, datetime

from app.modules.assistant.chat import UNKNOWN, respond

HERE = pathlib.Path(__file__).parent


async def evaluate() -> dict:
    cases = json.loads((HERE / "assistant_cases.json").read_text())["cases"]
    rows, passed, replaced = [], 0, 0
    for case in cases:
        answer, cited, _, _ = await respond(case["facts"], [tuple(e) for e in case["evidence"]],
                                            [tuple(h) for h in case.get("history", [])],
                                            case["question"])
        await asyncio.sleep(2)  # the free plan's per-minute limit
        low = answer.lower()
        replaced += answer == UNKNOWN
        if case["expect"] == "answer":
            ok = bool(cited) and all(w in low for w in case.get("must_mention", []))
        else:
            ok = not cited and not any(w in low for w in case.get("must_not_mention", []))
        passed += ok
        rows.append({"id": case["id"], "expect": case["expect"], "ok": ok, "cited": cited,
                     "answer": answer})
    return {"run_at": datetime.now(UTC).isoformat(), "cases": len(cases), "passed": passed,
            "replaced_by_checks": replaced, "rows": rows}


def main() -> None:
    result = asyncio.run(evaluate())
    (HERE / "last-assistant.json").write_text(json.dumps(result, indent=2))
    print(f"passed {result['passed']}/{result['cases']}; "  # noqa: T201
          f"answers replaced by the checks: {result['replaced_by_checks']}")
    for row in result["rows"]:
        print(f"{'ok  ' if row['ok'] else 'MISS'} {row['id']:<22} {row['cited']} "  # noqa: T201
              f"{row['answer'][:110]}")


if __name__ == "__main__":
    main()
