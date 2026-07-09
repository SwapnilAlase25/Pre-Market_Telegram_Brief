"""Assemble the final WhatsApp message. All numeric fields come from fetch_indices —
the LLM summary only ever fills the news section, never numbers."""
import html
from datetime import datetime

NA = "N/A"

FRIENDLY_NAMES = {
    "nifty": "Nifty",
    "gift_nifty": "GIFT Nifty",
    "dow": "Dow",
    "sp500": "S&P",
    "nasdaq": "Nasdaq",
    "ftse": "FTSE",
    "dax": "DAX",
    "nikkei": "Nikkei",
    "hsi": "HSI",
    "kospi": "Kospi",
}


def _move_emoji(change_pct: float) -> str:
    if change_pct > 0:
        return "🟢🔼"
    if change_pct < 0:
        return "🔴🔽"
    return "⚪️"


def _fmt_pct(indices: dict, key: str) -> str:
    if key not in indices:
        return f"{NA}"
    change_pct = indices[key]["change_pct"]
    return f"{change_pct:+.2f}% {_move_emoji(change_pct)}"


def _fmt_price(indices: dict, key: str) -> str:
    if key not in indices:
        return NA
    return f"{indices[key]['price']:,.2f}"


def format_message(indices: dict, failed_tickers: list[str], news_summary: str) -> str:
    now = datetime.now()
    date_str = now.strftime("%d %b %Y")
    day_str = now.strftime("%A")

    failed_str = ", ".join(FRIENDLY_NAMES.get(k, k) for k in failed_tickers) or "None"
    safe_news_summary = html.escape(news_summary)

    message = f"""<b>📊 Pre-Market Brief — {date_str}, {day_str}</b>

<b>🇮🇳 Indian Markets</b>
Nifty (prev close): {_fmt_price(indices, 'nifty')} ({_fmt_pct(indices, 'nifty')})
GIFT Nifty: {_fmt_price(indices, 'gift_nifty')} ({_fmt_pct(indices, 'gift_nifty')})

<b>🇺🇸 US Close</b>
Dow: {_fmt_pct(indices, 'dow')}
S&amp;P 500: {_fmt_pct(indices, 'sp500')}
Nasdaq: {_fmt_pct(indices, 'nasdaq')}

<b>🇪🇺 Europe Close</b>
FTSE: {_fmt_pct(indices, 'ftse')}
DAX: {_fmt_pct(indices, 'dax')}

<b>🌅 Asia (live)</b>
Nikkei: {_fmt_pct(indices, 'nikkei')}
HSI: {_fmt_pct(indices, 'hsi')}
Kospi: {_fmt_pct(indices, 'kospi')}

<b>📰 What's moving markets</b>
{safe_news_summary}

<b>⚠️ Data unavailable for:</b> {failed_str}"""

    return message


if __name__ == "__main__":
    dummy_indices = {
        "nifty": {"price": 24500.15, "change_pct": 0.35},
        "dow": {"price": 39000.0, "change_pct": -0.12},
    }
    print(format_message(dummy_indices, ["gift_nifty", "sp500"], "- Sample bullet"))
