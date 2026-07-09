"""Orchestrator: fetch_indices -> fetch_news -> summarize -> format -> send.

Each stage is isolated so a failure in news/summarization never blocks sending
the numeric data. If the whole pipeline blows up, we still try to send a bare
failure notice so a broken run is never silent.
"""
import logging
import sys

from fetch_indices import fetch_indices
from fetch_news import fetch_news
from format_message import format_message
from send_telegram import send_telegram_message
from summarize import summarize_headlines

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def build_brief() -> str:
    indices, failed = fetch_indices()

    try:
        headlines = fetch_news()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fetch_news raised unexpectedly: %s", exc)
        headlines = []

    try:
        news_summary = summarize_headlines(headlines)
    except Exception as exc:  # noqa: BLE001
        logger.warning("summarize_headlines raised unexpectedly: %s", exc)
        news_summary = "News summary unavailable."

    return format_message(indices, failed, news_summary)


def main() -> int:
    try:
        message = build_brief()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to build brief: %s", exc)
        try:
            send_telegram_message("⚠️ Pre-Market Brief failed to generate today. Check GitHub Actions logs.")
        except Exception as send_exc:  # noqa: BLE001
            logger.error("Also failed to send failure notice: %s", send_exc)
        return 1

    logger.info("Built message:\n%s", message)

    try:
        send_telegram_message(message)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send Telegram message: %s", exc)
        return 1

    logger.info("Brief sent successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
