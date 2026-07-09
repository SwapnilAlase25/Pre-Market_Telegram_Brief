"""Send the brief via the Telegram Bot API."""
import logging
import os
import sys

import requests

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20


def send_telegram_message(
    body_text: str,
    bot_token: str | None = None,
    chat_id: str | None = None,
) -> dict:
    """
    Send `body_text` to the configured Telegram chat.
    Raises on failure — callers should let this propagate so GitHub Actions
    marks the run as failed.
    """
    bot_token = bot_token or os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": body_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    resp = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)

    logger.info("Telegram API response [%s]: %s", resp.status_code, resp.text)

    if not resp.ok:
        raise RuntimeError(f"Telegram send failed [{resp.status_code}]: {resp.text}")

    return resp.json()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        result = send_telegram_message("Test message from send_telegram.py standalone run.")
        print(result)
    except Exception as exc:  # noqa: BLE001
        print(f"Send failed: {exc}", file=sys.stderr)
        sys.exit(1)
