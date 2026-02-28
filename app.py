import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf


DEFAULT_TICKERS = [
    "VUG", "VTI", "VOO", "QQQ", "TQQQ", "AMD", "TSLA", "MSFT", "KO", "BRK-B"
]

POSITIVE_WORDS = {
    "beat", "beats", "growth", "upgrade", "surge", "gain", "bullish", "strong",
    "record", "profit", "outperform", "buy", "rise", "improve", "positive",
}
NEGATIVE_WORDS = {
    "miss", "cuts", "downgrade", "drop", "fall", "bearish", "weak", "loss",
    "risk", "lawsuit", "decline", "sell", "negative", "warn", "warning",
}


st.set_page_config(page_title="ML Stock Tracker", page_icon="📈")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
            :root {
                --bg-main: #15181d;
                --bg-panel: #1c2027;
                --line: #2f3642;
                --text: #d9dee8;
                --text-muted: #98a3b5;
                --text-soft: #7d8899;
            }
            .stApp {
                background: var(--bg-main);
                color: var(--text);
                font-size: 12px;
            }
            .block-container {
                max-width: 980px;
                padding-top: 1rem;
                padding-bottom: 1.2rem;
            }
            .stButton > button {
                min-height: 2.35rem;
                border-radius: 6px;
                border: 1px solid var(--line);
                background: linear-gradient(180deg, #2a303a 0%, #242a33 100%);
                color: var(--text);
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.01em;
                white-space: normal;
                line-height: 1.25;
            }
            .stButton > button:hover {
                border-color: #465163;
                color: #eef2f8;
            }
            .stTextInput > div > div > input,
            .stSelectbox > div > div {
                border-radius: 6px;
                border: 1px solid var(--line);
                background: #181c23;
                color: var(--text);
                font-size: 11px;
            }
            .terminal-head {
                border: 1px solid var(--line);
                border-radius: 8px;
                background: linear-gradient(170deg, #20252d 0%, #1a1e25 100%);
                padding: 12px 14px;
                margin-bottom: 8px;
            }
            .head-kicker {
                color: var(--text-soft);
                font-size: 9px;
                letter-spacing: 0.18em;
                text-transform: uppercase;
                margin-bottom: 3px;
            }
            .head-title {
                color: #edf2f9;
                font-size: 17px;
                letter-spacing: 0.05em;
                font-weight: 700;
                margin-bottom: 2px;
            }
            .head-sub {
                color: var(--text-muted);
                font-size: 10px;
            }
            .status-row {
                margin-top: 6px;
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
            }
            .status-chip {
                border: 1px solid #3d4758;
                border-radius: 999px;
                padding: 2px 8px;
                font-size: 10px;
                color: #ccd5e4;
                background: #252c37;
            }
            .pro-panel {
                border: 1px solid var(--line);
                border-radius: 8px;
                background: var(--bg-panel);
                padding: 9px;
                margin-top: 9px;
            }
            .pro-head {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 8px;
                padding: 3px 3px 8px;
            }
            .pro-title {
                color: #e7edf8;
                font-size: 11px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                font-weight: 700;
            }
            .pro-sub {
                color: var(--text-soft);
                font-size: 10px;
            }
            .watchlist-chips {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
                margin: 6px 0;
            }
            .ticker-chip {
                border: 1px solid #3a4353;
                border-radius: 999px;
                padding: 2px 8px;
                font-size: 10px;
                background: #242c37;
            }
            .kpi-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 8px;
                margin-top: 6px;
            }
            .kpi {
                border: 1px solid var(--line);
                border-radius: 7px;
                padding: 8px;
                background: #20252e;
            }
            .kpi-label {
                font-size: 9px;
                letter-spacing: 0.09em;
                text-transform: uppercase;
                color: var(--text-soft);
                margin-bottom: 5px;
            }
            .kpi-value {
                font-size: 16px;
                color: #edf2f9;
                font-weight: 700;
            }
            .kpi-note {
                font-size: 9px;
                color: var(--text-muted);
            }
            .table-wrap {
                overflow-x: auto;
                border-top: 1px solid var(--line);
            }
            table.pro-table {
                width: 100%;
                border-collapse: collapse;
            }
            table.pro-table th {
                font-size: 9px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: var(--text-soft);
                font-weight: 600;
                text-align: left;
                padding: 7px 7px;
                border-bottom: 1px solid var(--line);
                background: #1f242d;
                position: sticky;
                top: 0;
            }
            table.pro-table td {
                font-size: 10px;
                color: var(--text);
                padding: 6px 7px;
                border-bottom: 1px solid #2a303a;
            }
            table.pro-table tr:hover td {
                background: #252c36;
            }
            .empty-note {
                border: 1px dashed #394253;
                border-radius: 6px;
                color: var(--text-muted);
                font-size: 10px;
                padding: 9px;
                margin: 3px;
            }
            .log-box {
                border: 1px solid var(--line);
                border-radius: 6px;
                padding: 8px;
                background: #171c24;
                min-height: 120px;
                max-height: 250px;
                overflow-y: auto;
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
                font-size: 10px;
                color: #bcc7da;
                line-height: 1.4;
                white-space: pre-wrap;
            }
            a {
                color: #afc1e4 !important;
                text-decoration: none !important;
            }
            a:hover {
                color: #d8e2f5 !important;
                text-decoration: underline !important;
            }
            @media (max-width: 700px) {
                .kpi-grid {
                    grid-template-columns: 1fr;
                }
            }
            @media (max-width: 920px) {
                div[data-testid="stHorizontalBlock"] {
                    flex-wrap: wrap;
                    gap: 0.55rem;
                }
                div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
                    min-width: 100% !important;
                    flex: 1 1 100% !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = DEFAULT_TICKERS.copy()
    if "last_refreshed" not in st.session_state:
        st.session_state.last_refreshed = None
    if "price_rows" not in st.session_state:
        st.session_state.price_rows = []
    if "analysis_rows" not in st.session_state:
        st.session_state.analysis_rows = []
    if "fetch_logs" not in st.session_state:
        st.session_state.fetch_logs = []
    if "network_status" not in st.session_state:
        st.session_state.network_status = "Not checked"
    if "news_rows" not in st.session_state:
        st.session_state.news_rows = []
    if "sentiment_trend_df" not in st.session_state:
        st.session_state.sentiment_trend_df = pd.DataFrame(columns=["Date", "Avg Sentiment"])
    if "sentiment_volume_df" not in st.session_state:
        st.session_state.sentiment_volume_df = pd.DataFrame(columns=["Date", "Positive", "Negative"])


def log_event(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.fetch_logs.append(f"[{timestamp}] {message}")
    if len(st.session_state.fetch_logs) > 300:
        st.session_state.fetch_logs = st.session_state.fetch_logs[-300:]


def normalize_ticker(raw: str) -> str:
    return raw.strip().upper().replace(" ", "")


def format_big_number(value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    return f"{value:,.0f}"


def yahoo_link(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{urllib.parse.quote(ticker)}"


def percent_to_float(raw_percent: str) -> float | None:
    if not raw_percent or raw_percent == "—":
        return None
    try:
        return float(raw_percent.replace("%", ""))
    except ValueError:
        return None


def safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
        if pd.isna(parsed):
            return None
        return parsed
    except (TypeError, ValueError):
        return None


def tokenized(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def simple_sentiment_score(text: str) -> float:
    words = tokenized(text)
    if not words:
        return 0.0
    pos = sum(1 for word in words if word in POSITIVE_WORDS)
    neg = sum(1 for word in words if word in NEGATIVE_WORDS)
    hits = pos + neg
    if hits == 0:
        return 0.0
    return (pos - neg) / hits


def check_yfinance_connectivity() -> tuple[bool, str]:
    try:
        chart_url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=5d&interval=1d"
        req = urllib.request.Request(chart_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = payload.get("chart", {}).get("result")
        if result:
            return True, "Yahoo chart API reachable (internet OK)."
        return False, "Yahoo chart API reachable but empty payload."
    except Exception as exc:
        return False, f"Yahoo chart API probe failed: {exc}"


def build_snapshot_row(
    ticker: str,
    stock_name: str,
    current_price: float | None,
    previous_close: float | None,
    day_low: float | None,
    day_high: float | None,
    open_price: float | None,
    volume: float | None,
    market_cap: float | None,
) -> dict:
    pct_change = None
    if current_price is not None and previous_close not in (None, 0):
        pct_change = ((current_price - previous_close) / previous_close) * 100

    link = yahoo_link(ticker)
    return {
        "Stock": f"<a href='{link}' target='_blank'>{stock_name}</a>",
        "Ticker": f"<a href='{link}' target='_blank'>{ticker}</a>",
        "Current Price": f"${current_price:,.2f}" if current_price is not None else "—",
        "% Change": f"{pct_change:+.2f}%" if pct_change is not None else "—",
        "Low (Today)": f"${day_low:,.2f}" if day_low is not None else "—",
        "High (Today)": f"${day_high:,.2f}" if day_high is not None else "—",
        "Open": f"${open_price:,.2f}" if open_price is not None else "—",
        "Volume": format_big_number(volume) if volume is not None else "—",
        "Market Cap": format_big_number(market_cap) if market_cap is not None else "—",
    }


def extract_market_slice(market_data: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if market_data.empty:
        return pd.DataFrame()

    if not isinstance(market_data.columns, pd.MultiIndex):
        return market_data.copy()

    columns = market_data.columns

    if ticker in columns.get_level_values(1):
        extracted = market_data.xs(ticker, axis=1, level=1, drop_level=True)
        return extracted if isinstance(extracted, pd.DataFrame) else extracted.to_frame()

    if ticker in columns.get_level_values(0):
        extracted = market_data[ticker]
        return extracted if isinstance(extracted, pd.DataFrame) else extracted.to_frame()

    return pd.DataFrame()


def fetch_yahoo_chart_quote(ticker: str) -> dict | None:
    encoded = urllib.parse.quote(ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=5d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result")
    if not result:
        return None

    node = result[0]
    meta = node.get("meta", {})
    quote_list = node.get("indicators", {}).get("quote", [])
    if not quote_list:
        return None

    quote = quote_list[0]

    def last_valid(values):
        if not values:
            return None
        for value in reversed(values):
            parsed = safe_float(value)
            if parsed is not None:
                return parsed
        return None

    current_price = safe_float(meta.get("regularMarketPrice")) or last_valid(quote.get("close"))
    previous_close = safe_float(meta.get("previousClose"))
    day_low = safe_float(meta.get("regularMarketDayLow")) or last_valid(quote.get("low"))
    day_high = safe_float(meta.get("regularMarketDayHigh")) or last_valid(quote.get("high"))
    open_price = safe_float(meta.get("regularMarketOpen")) or last_valid(quote.get("open"))
    volume = safe_float(meta.get("regularMarketVolume")) or last_valid(quote.get("volume"))
    market_cap = safe_float(meta.get("marketCap"))

    if current_price is None:
        return None

    return build_snapshot_row(
        ticker=ticker,
        stock_name=ticker,
        current_price=current_price,
        previous_close=previous_close,
        day_low=day_low,
        day_high=day_high,
        open_price=open_price,
        volume=volume,
        market_cap=market_cap,
    )


def fetch_with_yfinance_download(ticker: str) -> dict | None:
    history = yf.download(
        tickers=ticker,
        period="1mo",
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if history.empty or "Close" not in history.columns:
        return None

    valid = history.dropna(subset=["Close"])
    if valid.empty:
        return None

    current_row = valid.iloc[-1]
    previous_close = safe_float(valid.iloc[-2]["Close"]) if len(valid) > 1 else None
    return build_snapshot_row(
        ticker=ticker,
        stock_name=ticker,
        current_price=safe_float(current_row.get("Close")),
        previous_close=previous_close,
        day_low=safe_float(current_row.get("Low")),
        day_high=safe_float(current_row.get("High")),
        open_price=safe_float(current_row.get("Open")),
        volume=safe_float(current_row.get("Volume")),
        market_cap=None,
    )


def fetch_stock_snapshots_batch(tickers: list[str]) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    failures: list[str] = []

    log_event(f"Starting fetch for {len(tickers)} ticker(s): {', '.join(tickers)}")

    market_data = pd.DataFrame()
    try:
        market_data = yf.download(
            tickers=tickers,
            period="1mo",
            interval="1d",
            auto_adjust=False,
            group_by="column",
            progress=False,
            threads=False,
        )
        if market_data.empty:
            log_event("Batch yfinance download returned empty data frame.")
        else:
            log_event("Batch yfinance download succeeded.")
    except Exception as exc:
        log_event(f"Batch yfinance download failed: {exc}")

    for ticker in tickers:
        log_event(f"Fetching {ticker}...")
        slice_df = extract_market_slice(market_data, ticker)
        if not slice_df.empty and "Close" in slice_df.columns:
            valid = slice_df.dropna(subset=["Close"])
            if not valid.empty:
                current_row = valid.iloc[-1]
                previous_close = safe_float(valid.iloc[-2]["Close"]) if len(valid) > 1 else None
                row = build_snapshot_row(
                    ticker=ticker,
                    stock_name=ticker,
                    current_price=safe_float(current_row.get("Close")),
                    previous_close=previous_close,
                    day_low=safe_float(current_row.get("Low")),
                    day_high=safe_float(current_row.get("High")),
                    open_price=safe_float(current_row.get("Open")),
                    volume=safe_float(current_row.get("Volume")),
                    market_cap=None,
                )
                rows.append(row)
                log_event(f"{ticker}: loaded via yfinance batch.")
                continue

        try:
            y_row = fetch_with_yfinance_download(ticker)
            if y_row is not None:
                rows.append(y_row)
                log_event(f"{ticker}: loaded via yfinance single-symbol download.")
                continue
            log_event(f"{ticker}: yfinance single-symbol download empty.")
        except Exception as exc:
            log_event(f"{ticker}: yfinance single-symbol error ({exc}).")

        try:
            chart_row = fetch_yahoo_chart_quote(ticker)
            if chart_row is not None:
                rows.append(chart_row)
                log_event(f"{ticker}: loaded via direct Yahoo chart API.")
                continue
            log_event(f"{ticker}: direct Yahoo chart API returned empty payload.")
        except Exception as exc:
            log_event(f"{ticker}: direct Yahoo chart API error ({exc}).")

        failures.append(f"{ticker}: all live data paths failed")
        log_event(f"{ticker}: excluded (no live row returned).")

    log_event(f"Fetch completed. Live rows={len(rows)}, excluded={len(failures)}")
    return rows, failures


def run_ml_analysis(ticker: str) -> dict:
    hist = yf.download(
        tickers=ticker,
        period="6mo",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if hist.empty or len(hist) < 30 or "Close" not in hist.columns:
        raise ValueError("Not enough history for analysis")

    closes = hist["Close"].dropna()
    returns = closes.pct_change().dropna()
    x = np.arange(len(closes))
    slope = float(np.polyfit(x, np.asarray(closes, dtype=float), 1)[0])
    volatility = float(returns.std() * np.sqrt(252)) if not returns.empty else np.nan
    momentum = ((closes.iloc[-1] / closes.iloc[-20]) - 1) * 100 if len(closes) >= 20 else np.nan

    if pd.notna(momentum) and pd.notna(volatility):
        if momentum > 3 and volatility < 0.45 and slope > 0:
            signal = "Buy"
            confidence = "High"
        elif momentum < -3 or slope < 0:
            signal = "Sell"
            confidence = "Medium"
        else:
            signal = "Hold"
            confidence = "Medium"
    else:
        signal = "Hold"
        confidence = "Low"

    return {
        "Ticker": f"<a href='{yahoo_link(ticker)}' target='_blank'>{ticker}</a>",
        "Signal": signal,
        "Confidence": confidence,
        "Momentum (20d)": f"{momentum:+.2f}%" if pd.notna(momentum) else "—",
        "Volatility (Ann.)": f"{volatility:.2f}" if pd.notna(volatility) else "—",
    }


def fetch_news_sentiment(ticker: str) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    log_event(f"Loading news for {ticker}...")
    stock = yf.Ticker(ticker)
    news_items = stock.news or []

    if not news_items:
        log_event(f"{ticker}: no recent news returned by yfinance.")
        return [], pd.DataFrame(columns=["Date", "Avg Sentiment"]), pd.DataFrame(columns=["Date", "Positive", "Negative"])

    rows: list[dict] = []
    for item in news_items[:60]:
        title = item.get("title") or ""
        summary = item.get("summary") or ""
        publisher = item.get("publisher") or "Unknown"
        timestamp = item.get("providerPublishTime")

        if isinstance(timestamp, (int, float)):
            date_val = datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
        else:
            date_val = datetime.now(timezone.utc).date()

        score = simple_sentiment_score(f"{title} {summary}")
        if score > 0.15:
            sentiment = "Positive"
        elif score < -0.15:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        rows.append(
            {
                "Date": str(date_val),
                "Publisher": publisher,
                "Headline": title or "(No title)",
                "Sentiment": sentiment,
                "Score": round(score, 3),
            }
        )

    news_df = pd.DataFrame(rows)
    trend_df = (
        news_df.groupby("Date", as_index=False)
        .agg(**{"Avg Sentiment": ("Score", "mean")})
        .sort_values("Date")
    )

    volume_df = pd.DataFrame(
        (
            news_df[news_df["Sentiment"].isin(["Positive", "Negative"])]
            .groupby(["Date", "Sentiment"], as_index=False)
            .size()
            .pivot(index="Date", columns="Sentiment", values="size")
            .fillna(0)
            .reset_index()
            .sort_values("Date")
        )
    )

    if "Positive" not in volume_df.columns:
        volume_df.loc[:, "Positive"] = 0
    if "Negative" not in volume_df.columns:
        volume_df.loc[:, "Negative"] = 0

    log_event(f"{ticker}: processed {len(news_df)} news item(s) for sentiment.")
    return rows, trend_df, volume_df[["Date", "Positive", "Negative"]]


def render_watchlist_chips(watchlist: list[str]) -> None:
    chip_html = "".join(
        f"<span class='ticker-chip'><a href='{yahoo_link(ticker)}' target='_blank'>{ticker}</a></span>"
        for ticker in watchlist
    )
    st.markdown(f"<div class='watchlist-chips'>{chip_html}</div>", unsafe_allow_html=True)


def render_kpis(rows: list[dict]) -> None:
    changes = [percent_to_float(row.get("% Change", "—")) for row in rows]
    valid_changes = [value for value in changes if value is not None]
    gainers = len([value for value in valid_changes if value > 0])
    losers = len([value for value in valid_changes if value < 0])
    avg_move = (sum(valid_changes) / len(valid_changes)) if valid_changes else 0.0
    tracked = len(rows)

    st.markdown(
        """
        <div class='kpi-grid'>
            <div class='kpi'>
                <div class='kpi-label'>Tracked Symbols</div>
                <div class='kpi-value'>__TRACKED__</div>
                <div class='kpi-note'>Rows currently loaded</div>
            </div>
            <div class='kpi'>
                <div class='kpi-label'>Average Move</div>
                <div class='kpi-value'>__AVG__</div>
                <div class='kpi-note'>Daily percentage change</div>
            </div>
            <div class='kpi'>
                <div class='kpi-label'>Gainers</div>
                <div class='kpi-value'>__GAINERS__</div>
                <div class='kpi-note'>Above 0%</div>
            </div>
            <div class='kpi'>
                <div class='kpi-label'>Losers</div>
                <div class='kpi-value'>__LOSERS__</div>
                <div class='kpi-note'>Below 0%</div>
            </div>
        </div>
        """.replace("__TRACKED__", str(tracked))
        .replace("__AVG__", f"{avg_move:+.2f}%")
        .replace("__GAINERS__", str(gainers))
        .replace("__LOSERS__", str(losers)),
        unsafe_allow_html=True,
    )


def render_html_table(rows: list[dict], title: str, subtitle: str, empty_text: str) -> None:
    st.markdown(
        f"""
        <section class='pro-panel'>
            <div class='pro-head'>
                <div class='pro-title'>{title}</div>
                <div class='pro-sub'>{subtitle}</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    if not rows:
        st.markdown(f"<div class='empty-note'>{empty_text}</div></section>", unsafe_allow_html=True)
        return

    frame = pd.DataFrame(rows)
    table_html = frame.to_html(index=False, escape=False, classes="pro-table")
    st.markdown(f"<div class='table-wrap'>{table_html}</div></section>", unsafe_allow_html=True)


inject_styles()
init_state()

refreshed = st.session_state.last_refreshed or "—"
st.markdown(
    f"""
    <section class='terminal-head'>
        <div class='head-kicker'>Institutional Trading Workspace</div>
        <div class='head-title'>ML STOCK TRACKER TERMINAL</div>
        <div class='head-sub'>Responsive trading dashboard.</div>
        <div class='status-row'>
            <span class='status-chip'>Last Refresh: {refreshed}</span>
            <span class='status-chip'>Network: {st.session_state.network_status}</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

if st.button("Refresh", use_container_width=True):
    st.session_state.last_refreshed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.fetch_logs = []
    log_event("Dashboard refreshed.")
    ok, detail = check_yfinance_connectivity()
    st.session_state.network_status = "Online" if ok else "Unreachable"
    log_event(detail)

top_left, top_right = st.columns([3, 2])
with top_left:
    st.markdown(
        "<section class='pro-panel'><div class='pro-head'><div class='pro-title'>Control Panel</div><div class='pro-sub'>Execution controls and symbol management</div></div>",
        unsafe_allow_html=True,
    )
    new_tickers = st.text_input("Add symbols (comma-separated)", placeholder="AAPL, NVDA, SPY")
    if st.button("Add Symbols", use_container_width=True):
        candidates = [normalize_ticker(ticker) for ticker in new_tickers.split(",") if normalize_ticker(ticker)]
        merged = st.session_state.watchlist.copy()
        for ticker in candidates:
            if ticker not in merged:
                merged.append(ticker)
                log_event(f"Added symbol: {ticker}")
        st.session_state.watchlist = merged

    render_watchlist_chips(st.session_state.watchlist)

    fetch_clicked = st.button("Obtain Stock Price & yfinance Info", use_container_width=True)
    analysis_clicked = st.button("Start Analysis / ML", use_container_width=True)
    st.markdown("</section>", unsafe_allow_html=True)

with top_right:
    st.markdown(
        "<section class='pro-panel'><div class='pro-head'><div class='pro-title'>Network & News</div><div class='pro-sub'>Connectivity and sentiment controls</div></div>",
        unsafe_allow_html=True,
    )
    net_clicked = st.button("Check yfinance Network", use_container_width=True)
    selected_ticker = st.selectbox(
        "Selected stock for news sentiment",
        options=st.session_state.watchlist,
        index=0 if st.session_state.watchlist else None,
    )
    selected_ticker = str(selected_ticker) if selected_ticker is not None else ""
    news_clicked = st.button("Load News Sentiment", use_container_width=True)
    st.markdown("</section>", unsafe_allow_html=True)

log_col, mini_col = st.columns([3, 2])
with log_col:
    st.markdown(
        "<section class='pro-panel'><div class='pro-head'><div class='pro-title'>Fetch Log</div><div class='pro-sub'>Execution trace</div></div>",
        unsafe_allow_html=True,
    )
    if st.session_state.fetch_logs:
        logs_text = "\n".join(st.session_state.fetch_logs[-120:])
        st.markdown(f"<div class='log-box'>{logs_text}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='log-box'>No execution logs yet.</div>", unsafe_allow_html=True)
    st.markdown("</section>", unsafe_allow_html=True)

with mini_col:
    st.markdown(
        "<section class='pro-panel'><div class='pro-head'><div class='pro-title'>Quick Stats</div><div class='pro-sub'>Live market snapshot</div></div>",
        unsafe_allow_html=True,
    )
    render_kpis(st.session_state.price_rows)
    st.markdown("</section>", unsafe_allow_html=True)

if net_clicked:
    ok, detail = check_yfinance_connectivity()
    st.session_state.network_status = "Online" if ok else "Unreachable"
    log_event(detail)
    if ok:
        st.success(detail)
    else:
        st.error(detail)

if fetch_clicked:
    with st.spinner("Fetching live prices and market fields..."):
        rows, failures = fetch_stock_snapshots_batch(st.session_state.watchlist)
        st.session_state.price_rows = rows

    if rows:
        st.success(f"Loaded {len(rows)} live row(s).")
    else:
        st.error("No live rows returned. Check network/proxy or Yahoo availability.")

    if failures:
        st.warning("Excluded tickers (no live data): " + " | ".join(failures))

if analysis_clicked:
    with st.spinner("Running analysis engine..."):
        analysis_rows = []
        analysis_failures = []
        for ticker in st.session_state.watchlist:
            log_event(f"Analyzing {ticker}...")
            try:
                analysis_rows.append(run_ml_analysis(ticker))
            except Exception as exc:
                analysis_failures.append(f"{ticker}: {exc}")
                log_event(f"{ticker}: analysis failed ({exc}).")
        st.session_state.analysis_rows = analysis_rows

    st.success(f"Completed analysis for {len(st.session_state.analysis_rows)} ticker(s).")
    if analysis_failures:
        st.warning("Some analysis runs failed: " + " | ".join(analysis_failures))

if news_clicked:
    with st.spinner(f"Loading recent news and sentiment for {selected_ticker}..."):
        try:
            rows, trend_df, volume_df = fetch_news_sentiment(selected_ticker)
            st.session_state.news_rows = rows
            st.session_state.sentiment_trend_df = trend_df
            st.session_state.sentiment_volume_df = volume_df
            st.success(f"News sentiment loaded for {selected_ticker} ({len(rows)} item(s)).")
        except Exception as exc:
            st.session_state.news_rows = []
            st.session_state.sentiment_trend_df = pd.DataFrame(columns=["Date", "Avg Sentiment"])
            st.session_state.sentiment_volume_df = pd.DataFrame(columns=["Date", "Positive", "Negative"])
            log_event(f"{selected_ticker}: news sentiment failed ({exc}).")
            st.error(f"News sentiment loading failed: {exc}")

render_html_table(
    st.session_state.price_rows,
    "Price Dashboard",
    "Live online rows only (no synthetic fallback)",
    "No live price rows loaded yet. Use 'Obtain Stock Price & yfinance Info'.",
)

render_html_table(
    st.session_state.analysis_rows,
    "Analysis / ML Output",
    "Momentum, annualized volatility, and rule-based signal",
    "No analysis data loaded yet. Use 'Start Analysis / ML'.",
)

st.markdown(
    "<section class='pro-panel'><div class='pro-head'><div class='pro-title'>News Sentiment Intelligence</div><div class='pro-sub'>Generated only for selected stock on explicit request</div></div>",
    unsafe_allow_html=True,
)

if st.session_state.sentiment_trend_df.empty and st.session_state.sentiment_volume_df.empty:
    st.markdown(
        "<div class='empty-note'>No sentiment data loaded yet. Select a stock and click 'Load News Sentiment'.</div>",
        unsafe_allow_html=True,
    )
else:
    st.caption("Average sentiment trend by date")
    trend_chart = st.session_state.sentiment_trend_df.set_index("Date") if not st.session_state.sentiment_trend_df.empty else pd.DataFrame()
    if trend_chart.empty:
        st.info("No trend values to plot.")
    else:
        st.line_chart(trend_chart)

    st.caption("Positive vs negative news volume by date")
    volume_chart = st.session_state.sentiment_volume_df.set_index("Date") if not st.session_state.sentiment_volume_df.empty else pd.DataFrame()
    if volume_chart.empty:
        st.info("No volume values to plot.")
    else:
        st.bar_chart(volume_chart[["Positive", "Negative"]])

st.markdown("</section>", unsafe_allow_html=True)

render_html_table(
    st.session_state.news_rows,
    "Recent News Sentiment Table",
    "Headline-level sentiment scores and publisher metadata",
    "No news rows available for the selected stock.",
)
