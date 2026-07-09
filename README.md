# Pre-Market Brief

Daily automated Telegram message delivered ~8:30 AM IST, before the 9:15 AM
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
  format_message.py       # assembles final message text
  send_telegram.py        # Telegram Bot API POST
.github/workflows/daily-brief.yml
```

## Setup

### 1. Telegram bot

1. In Telegram, message **@BotFather** → `/newbot` → follow the prompts
   (choose a name and a username ending in `bot`).
2. BotFather replies with a token like `123456789:AAExampleTokenHere` —
   that's `TELEGRAM_BOT_TOKEN`.
3. Message your new bot directly (search its username, hit Start) so it can
   message you back — a bot cannot message you until you've messaged it
   first.
4. Get your chat ID: visit
   `https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates` in a
   browser after sending the bot a message. Look for `"chat":{"id":...}` in
   the JSON response — that number (can be negative) is `TELEGRAM_CHAT_ID`.

No approval wait, no template — works immediately.

### 2. OpenRouter

Create an account at openrouter.ai, generate an API key, and note a free
model name (default: `deepseek/deepseek-chat-v3.1:free`). The model is
configurable via the `OPENROUTER_MODEL` env var in case the free model is
deprecated.

### 3. News source

Get a free API key from [NewsAPI.org](https://newsapi.org).

### 4. GitHub secrets

Add these under Settings → Secrets and variables → Actions:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENROUTER_API_KEY`
- `NEWS_API_KEY`

Optionally set `OPENROUTER_MODEL` as a repo variable or secret if you need
to override the default model.

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

# 4. Telegram delivery (sends a real test message)
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx python send_telegram.py

# 5. Full pipeline, locally
TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx \
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
  bare "brief failed" Telegram notice and exits non-zero so the GitHub
  Actions run is flagged as failed.

## Known constraints

- GIFT Nifty has no reliable `yfinance` ticker; `fetch_indices.py` tries a
  couple of fallback symbols and marks it unavailable if all fail.
- Cron is scheduled a bit earlier than the 8:30 AM IST target to absorb
  GitHub Actions scheduling lag.
- WhatsApp delivery (via Meta Cloud API) is on hold pending Meta Business
  verification; Telegram is the interim delivery channel. The pipeline can
  be re-pointed at WhatsApp later by swapping `send_telegram.py` back for a
  Meta Cloud API sender in `main.py`.
