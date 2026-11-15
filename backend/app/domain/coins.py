"""TelCoin fraud rules with exact answers (technical documentation 9.3). Pure functions."""

DAILY_CAP = 500
BURST_COUNT = 20
BURST_WINDOW_SECONDS = 5 * 60


def capped_amount(amount: int, earned_today_capped: int, counts_toward_cap: bool) -> int:
    """At most 500 coins a day from reviews, photos and flags. Returns what may still be awarded."""
    if not counts_toward_cap:
        return amount
    return max(0, min(amount, DAILY_CAP - earned_today_capped))


def is_burst(actions_in_window: int) -> bool:
    """20 capped actions inside five minutes opens a fraud hold."""
    return actions_in_window >= BURST_COUNT


def streak_multiplier(consecutive_days: int) -> int:
    """Daily sign-in doubles after a 7-day streak."""
    return 2 if consecutive_days > 7 else 1
