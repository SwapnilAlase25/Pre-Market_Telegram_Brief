# Architecture

## Design rule

**The LLM never touches numbers.** All index prices/percentages are fetched
via `yfinance` and a deterministic bias calculation, then slotted into a
fixed message template. The OpenRouter model only ever summarizes news
headline *text* — it never sees or generates index data.

## Flow

```mermaid
flowchart TD
    CRON["⏰ GitHub Actions cron\nMon–Fri 02:45 UTC (8:15 AM IST)\n+ manual workflow_dispatch"]
    CRON --> MAIN["main.py\norchestrator"]

    subgraph DATA["Numeric data path — never touched by the LLM"]
        MAIN --> FI["fetch_indices.py\nyfinance fast_info,\nper-ticker isolation,\n±15% sanity clamp"]
        FI --> IDX[("Nifty, GIFT Nifty*, Dow,\nS&P, Nasdaq, FTSE, DAX,\nNikkei, HSI, Kospi")]
        IDX --> BIAS["market_bias.py\nweighted Bullish/Bearish/\nSideways verdict\n(pure arithmetic)"]
    end

    subgraph NEWS["News path — LLM only touches text"]
        MAIN --> FN["fetch_news.py\nNewsAPI, finance-domain\nallowlist, title-relevance\nfilter"]
        FN --> HL[("Headlines\ntitle + source")]
        HL --> SUM["summarize.py\nOpenRouter free model\n15s timeout"]
        SUM -->|success| BULLETS["3-4 bullet summary"]
        SUM -->|failure/timeout/empty| FALLBACK["raw headline list\n(capped to 4)"]
    end

    IDX --> FMT["format_message.py\nfixed template,\nHTML bold + move emojis"]
    BIAS --> FMT
    BULLETS --> FMT
    FALLBACK --> FMT

    FMT --> TG["send_telegram.py\nTelegram Bot API\nsendMessage (HTML)"]
    TG --> USER["📱 Telegram chat"]

    MAIN -.pipeline error.-> FAIL["⚠️ bare failure notice\nsent via Telegram\n+ non-zero exit"]
    FAIL -.-> TG
```

`*` GIFT Nifty has no reliable free data source (it trades on NSE IX in GIFT
City, not covered by `yfinance` or Groww); currently reported as `N/A`.

## Failure isolation

- Each index ticker is fetched independently — one dead/implausible value is
  marked "unavailable" rather than blocking the rest of the brief.
- News fetch and summarization failures fall back gracefully (empty list →
  raw headlines → generic "no headlines" message) and never block delivery
  of the numeric data.
- If the whole pipeline throws unexpectedly, `main.py` still attempts to
  send a bare "brief failed, check logs" Telegram message and exits
  non-zero so the GitHub Actions run is flagged red.

## Secrets

All credentials are injected as GitHub Actions repo secrets, never
hardcoded: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `OPENROUTER_API_KEY`,
`NEWS_API_KEY`.
