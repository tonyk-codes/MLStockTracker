# ML Stock Tracker

A machine-learning-powered stock analysis dashboard served via GitHub Pages.

## Strategies

| Strategy | Description |
|---|---|
| **MA Golden Cross** | 50-day vs 200-day SMA crossover detection (Golden Cross / Death Cross) |
| **Sentiment Analysis** | FinBERT (HuggingFace) + lexicon fallback on recent news headlines |
| **FinRL-Inspired Signals** | Composite score from momentum, RSI, MACD, Bollinger Bands, volatility, Sharpe ratio |
| **Correlation Analysis** | 3-month return correlation matrix between all tracked stocks |

## How It Works

1. **GitHub Actions** runs `scripts/analyze.py` (manual trigger via `workflow_dispatch`)
2. The script fetches data from Yahoo Finance, runs all strategies, and outputs `data/analysis.json`
3. **GitHub Pages** serves the static dashboard (`index.html`) that reads the JSON

## Setup

### Repository Secrets

| Secret | Required | Description |
|---|---|---|
| `GH_TOKEN_ACTIONS` | Yes | GitHub token for pushing analysis results |
| `HF_TOKEN` | No | HuggingFace API token for FinBERT sentiment (falls back to lexicon) |

### GitHub Pages

1. Go to **Settings → Pages**
2. Set source to **Deploy from a branch**
3. Select `main` branch, root `/`

### Running Analysis

1. Go to **Actions → ML Stock Analysis**
2. Click **Run workflow**
3. Wait for completion — results appear on the dashboard

## Project Structure

```
├── index.html              # Dashboard (GitHub Pages entry)
├── css/style.css           # Styles
├── js/app.js               # Dashboard logic
├── scripts/analyze.py      # ML analysis pipeline
├── data/analysis.json      # Generated analysis data
├── requirements.txt        # Python dependencies
├── .github/workflows/
│   └── analyze.yml         # GitHub Actions workflow
└── README.md
```

## Tracked Stocks

The watchlist includes 50+ symbols: major US equities (AAPL, MSFT, GOOGL, META, NVDA, TSLA), ETFs (QQQ, VOO, VTI, SCHD), leveraged products (TQQQ, SQQQ, TSLL, NVDL), crypto (BTC-USD, ETH-USD), and Hong Kong stocks.

