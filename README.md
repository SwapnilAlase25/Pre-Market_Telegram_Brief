# Pre-Market WhatsApp Brief

Daily automated WhatsApp message delivered ~8:30 AM IST, before the 9:15 AM
market open — Nifty prev close, US/Europe close, live SE Asia morning
session, and an LLM-summarized news digest.

## Design rule

**The LLM never touches numbers.** All index values are fetched via
`yfinance` and hardcoded into the message template in `format_message.py`.
The OpenRouter model only summarizes news headline text. This separation is
intentional — do not have the LLM draft the whole message from raw data.

## Repo structure

```
src/
  main.py              # orchestrator
  fetch_indices.py      # yfinance calls for Nifty, GIFT Nifty, US/Europe/Asia indices
  fetch_news.py          # NewsAPI headlines, India/market relevant
  summarize.py            # OpenRouter call — news only, 3-4 bullets
  format_message.py       # assembles final WhatsApp text
  send_whatsapp.py        # Meta WhatsApp Cloud API POST
.github/workflows/daily-brief.yml
```

## Setup

### 1. Meta WhatsApp Business Cloud API

1. Create a Meta Business Manager account and set up WhatsApp Business
   Cloud API (a test number works for personal use).
2. Submit a message template named `premarket_brief` for approval, with a
   single body placeholder, e.g.:
   ```
   {{1}}
   ```
   Approval can take 1-2 days — start this first.
3. Note your `WHATSAPP_TOKEN` (permanent access token), `WHATSAPP_PHONE_ID`,
   and `WHATSAPP_TO_NUMBER` (your number, in international format).

### 2. OpenRouter

Create an account at openrouter.ai, generate an API key, and note a free
model name (default: `deepseek/deepseek-chat-v3.1:free`). The model is
configurable via the `OPENROUTER_MODEL` env var in case the free model is
deprecated.

### 3. News source

Get a free API key from [NewsAPI.org](https://newsapi.org).

### 4. GitHub secrets

Add these under Settings → Secrets and variables → Actions:

- `WHATSAPP_TOKEN`
- `WHATSAPP_PHONE_ID`
- `WHATSAPP_TO_NUMBER`
- `OPENROUTER_API_KEY`
- `NEWS_API_KEY`

Optionally set `OPENROUTER_MODEL` / `WHATSAPP_TEMPLATE_NAME` as repo
variables or secrets if you need to override the defaults.

## Testing (do in this order)

```bash
pip install -r requirements.txt
cd src

# 1. Indices
python fetch_indices.py

# 2. News
NEWS_API_KEY=xxx python fetch_news.py

# 3. Summarization
OPENROUTER_API_KEY=xxx python summarize.py

# 4. WhatsApp delivery (sends a real test message)
WHATSAPP_TOKEN=xxx WHATSAPP_PHONE_ID=xxx WHATSAPP_TO_NUMBER=xxx python send_whatsapp.py

# 5. Full pipeline, locally
WHATSAPP_TOKEN=xxx WHATSAPP_PHONE_ID=xxx WHATSAPP_TO_NUMBER=xxx \
OPENROUTER_API_KEY=xxx NEWS_API_KEY=xxx python main.py
```

Then push, add the GitHub secrets, and trigger the workflow manually via
`workflow_dispatch` before relying on the cron schedule.

## Failure behavior

- Each index fetch is independently isolated — one dead ticker doesn't kill
  the brief; it's listed under "Data unavailable for" instead.
- If news fetch or summarization fails, the brief still sends with a
  fallback line instead of blocking delivery.
- If the whole pipeline fails unexpectedly, `main.py` attempts to send a
  bare "brief failed" WhatsApp notice and exits non-zero so the GitHub
  Actions run is flagged as failed.

## Known constraints

- Only the official Meta WhatsApp Cloud API is used — no unofficial
  libraries (Baileys, whatsapp-web.js).
- GIFT Nifty has no reliable `yfinance` ticker; `fetch_indices.py` tries a
  couple of fallback symbols and marks it unavailable if all fail.
- Cron is scheduled a bit earlier than the 8:30 AM IST target to absorb
  GitHub Actions scheduling lag.
