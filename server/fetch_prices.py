from datetime import datetime, timezone
import yfinance as yf

# Keep in sync with app.js tickers and Yahoo Finance symbols
TICKERS = {
    "VUG": "VUG",
    "VTI": "VTI",
    "VOO": "VOO",
    "SSO": "SSO",
    "QQQ": "QQQ",
    "TQQQ": "TQQQ",

    "AMD": "AMD",
    "AMDL": "AMDL",
    "TSLL": "TSLL",
    "TSLA": "TSLA",
    "METU": "METU",
    "MSFT": "MSFT",
    "MSFU": "MSFU",
    "NVDL": "NVDL",

    "KO": "KO",

    # Display as BRKB but Yahoo symbol is BRK-B
    "BRKB": "BRK-B",
    "BRKU": "BRKU",

    "LULU": "LULU",
    "NKE": "NKE",
}


def _pick(info, *keys):
    for k in keys:
        if k in info and info[k] is not None:
            return info[k]
    return None


def fetch_prices():
    rows = {}

    # yfinance supports batch download, but we want pre/post data, so use Ticker.info.
    for display_ticker, yf_symbol in TICKERS.items():
        t = yf.Ticker(yf_symbol)
        info = {}
        try:
            info = t.info or {}
        except Exception:
            info = {}

        regular = _pick(info, "regularMarketPrice")
        pre = _pick(info, "preMarketPrice")
        post = _pick(info, "postMarketPrice")
        currency = _pick(info, "currency", "financialCurrency")

        rows[display_ticker] = {
            "regular": regular,
            "pre": pre,
            "post": post,
            "currency": currency,
        }

    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }
