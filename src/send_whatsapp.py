"""Send the brief via the official Meta WhatsApp Cloud API (template message)."""
import logging
import os
import sys

import requests

logger = logging.getLogger(__name__)

WHATSAPP_API_VERSION = "v20.0"
TEMPLATE_NAME = "premarket_brief"
TIMEOUT_SECONDS = 20


def send_whatsapp_template(
    body_text: str,
    token: str | None = None,
    phone_id: str | None = None,
    to_number: str | None = None,
    template_name: str | None = None,
) -> dict:
    """
    Send `body_text` as the single placeholder of the approved `premarket_brief`
    template. Raises on failure — callers should let this propagate so GitHub
    Actions marks the run as failed.
    """
    token = token or os.environ["WHATSAPP_TOKEN"]
    phone_id = phone_id or os.environ["WHATSAPP_PHONE_ID"]
    to_number = to_number or os.environ["WHATSAPP_TO_NUMBER"]
    template_name = template_name or os.environ.get("WHATSAPP_TEMPLATE_NAME", TEMPLATE_NAME)

    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "en"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": body_text}],
                }
            ],
        },
    }

    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )

    logger.info("WhatsApp API response [%s]: %s", resp.status_code, resp.text)

    if not resp.ok:
        raise RuntimeError(f"WhatsApp send failed [{resp.status_code}]: {resp.text}")

    return resp.json()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        result = send_whatsapp_template("Test message from send_whatsapp.py standalone run.")
        print(result)
    except Exception as exc:  # noqa: BLE001
        print(f"Send failed: {exc}", file=sys.stderr)
        sys.exit(1)
