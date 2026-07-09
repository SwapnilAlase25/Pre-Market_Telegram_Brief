"""Summarize headlines via OpenRouter. Text-only task — never handles index numbers."""
import logging
import os

import requests

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-chat-v3.1:free"
TIMEOUT_SECONDS = 15
MAX_FALLBACK_HEADLINES = 4

SYSTEM_PROMPT = (
    "Summarize these headlines in 3-4 bullets, prioritizing anything likely to move "
    "Indian equity markets today. Ignore and drop any headline that is not relevant "
    "to Indian markets, global macro, or major asset classes (e.g. sports, crypto "
    "trivia, unrelated corporate PR). If none of the headlines are relevant, say "
    "'No market-moving headlines today.' Do not invent facts not in the headlines. "
    "Do not include numbers not present in the source text."
)


def _fallback_bullets(headlines: list[dict]) -> str:
    """Raw headline listing, used if the LLM call fails or headlines are empty."""
    if not headlines:
        return "No market-moving headlines available."
    return "\n".join(
        f"- {h['title']} ({h['source']})" for h in headlines[:MAX_FALLBACK_HEADLINES]
    )


def summarize_headlines(
    headlines: list[dict],
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    """
    Summarize headlines into 3-4 bullets via OpenRouter.
    Falls back to a raw headline listing on any failure, timeout, or empty response —
    this step must never block message delivery.
    """
    if not headlines:
        return _fallback_bullets(headlines)

    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)

    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set; falling back to raw headlines")
        return _fallback_bullets(headlines)

    headline_text = "\n".join(f"- [{h['source']}] {h['title']}" for h in headlines)

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": headline_text},
                ],
            },
            timeout=TIMEOUT_SECONDS,
        )
        if not resp.ok:
            logger.warning("OpenRouter returned %s: %s", resp.status_code, resp.text[:500])
            return _fallback_bullets(headlines)
        data = resp.json()
        if "choices" not in data:
            logger.warning("OpenRouter response missing 'choices': %s", str(data)[:500])
            return _fallback_bullets(headlines)
        content = data["choices"][0]["message"]["content"].strip()
        if not content:
            logger.warning("OpenRouter returned an empty summary; falling back to raw headlines")
            return _fallback_bullets(headlines)
        return content
    except Exception as exc:  # noqa: BLE001
        logger.warning("Summarization failed, falling back to raw headlines: %s", exc)
        return _fallback_bullets(headlines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dummy = [
        {"title": "Fed holds rates steady, signals caution on inflation", "source": "Reuters"},
        {"title": "Crude oil prices rise 2% on supply concerns", "source": "ET"},
    ]
    print(summarize_headlines(dummy))
