"""Deterministic bullish/bearish/sideways call from index data.

This is pure arithmetic on numbers already fetched by fetch_indices — the
LLM is never involved in this calculation, per the project's core rule that
index-derived numbers/verdicts must never be model-generated.
"""

# Weighted toward what's most predictive of today's Indian market open:
# live Asia session > overnight US close > overnight Europe close.
WEIGHTS = {
    "nikkei": 1.5,
    "hsi": 1.5,
    "kospi": 1.5,
    "dow": 1.0,
    "sp500": 1.0,
    "nasdaq": 1.0,
    "ftse": 0.5,
    "dax": 0.5,
}

BULLISH_THRESHOLD = 0.3
BEARISH_THRESHOLD = -0.3


def compute_bias(indices: dict) -> tuple[str, str]:
    """
    Returns (label, emoji) — one of Bullish/Bearish/Sideways, or
    ("Insufficient data", "⚪️") if too few indices are available to call it.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for key, weight in WEIGHTS.items():
        if key in indices:
            weighted_sum += indices[key]["change_pct"] * weight
            total_weight += weight

    if total_weight == 0:
        return "Insufficient data", "⚪️"

    score = weighted_sum / total_weight

    if score >= BULLISH_THRESHOLD:
        return "Bullish", "🟢📈"
    if score <= BEARISH_THRESHOLD:
        return "Bearish", "🔴📉"
    return "Sideways", "🟡➡️"


if __name__ == "__main__":
    dummy = {
        "nikkei": {"change_pct": -2.11},
        "hsi": {"change_pct": 2.99},
        "kospi": {"change_pct": -5.35},
        "dow": {"change_pct": 0.30},
        "sp500": {"change_pct": 0.65},
        "nasdaq": {"change_pct": 0.91},
        "ftse": {"change_pct": -0.16},
        "dax": {"change_pct": 0.89},
    }
    print(compute_bias(dummy))
