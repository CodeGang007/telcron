"""DEF-118 / CT-003 D: the earn cards say what the rules are and mark earns nobody can do yet."""

from helpers import API, verified_user


async def test_ways_to_earn_follow_d4_and_mark_unavailable_earns(client):
    _, _, member = await verified_user(client)
    earns = {w["code"]: w for w in
             (await client.get(f"{API}/rewards", headers=member)).json()["ways_to_earn"]}

    # Level 1 is the email code alone (D4, ADR-006); there is no phone check to promise.
    assert earns["level1_verified"]["label"] == "Verify your email"
    # The streak cards agree with the rule: 5 a day, 10 a day from day 7 (amounts from the rules).
    assert earns["login_streak"]["label"] == "Sign in each day"
    assert earns["login_streak_7plus"]["label"] == "Sign in each day from day 7 of a streak"
    assert (earns["login_streak"]["amount"], earns["login_streak_7plus"]["amount"]) == (5, 10)

    # Photos (WO-007), identity checks (WO-010) and referrals (phase two) cannot be done today.
    unavailable = {code for code, w in earns.items() if w["available"] is False}
    assert unavailable == {"photo", "level2_verified", "referral"}
    assert all(w["available"] is True for code, w in earns.items() if code not in unavailable)
