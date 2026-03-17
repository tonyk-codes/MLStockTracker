"""ML Stock Tracker with Our World in Data inspired layout."""

from __future__ import annotations

import json
import math
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------------
# WATCHLIST DEFAULTS (from user CSV attachment)
# ---------------------------------------------------------------------------
RAW_WATCHLIST = [
    "AMDL.US", "GGLL.US", "MSFU.US", "QNCX.US", "BRK.B.US", "AMD.US", "OXY.US",
    "AEG.US", "GOOGL.US", "BABA.US", "BABX.US", "TSLA.US", "SQQQ.US", "HIMZ.US",
    "LULG.US", "AMZU.US", "NFXL.US", "BRKU.US", "PYPG.US", "ETHUSD.CC", "AGQ.US",
    "GALDY.US", "BTCUSD.CC", "INTW.US", "KO.US", "NVDA.US", "01881.HK", "AAPU.US",
    "GOOG.US", "MSFT.US", "SCHD.US", "VT.US", "GME.US", "SSO.US", "LCDL.US",
    "TSLL.US", "METU.US", "META.US", "VUG.US", "NVDL.US", "SOXS.US", "UNHG.US",
    "UNH.US", "LULU.US", "AAPL.US", "NKE.US", "QQQ.US", "VOO.US", "VTI.US",
    "TQQQ.US", "LCID.US",
]

POSITIVE_WORDS = {
    "beat", "beats", "growth", "upgrade", "surge", "gain", "bullish", "strong",
    "record", "profit", "outperform", "buy", "rise", "improve", "positive",
}
NEGATIVE_WORDS = {
    "miss", "cuts", "downgrade", "drop", "fall", "bearish", "weak", "loss",
    "risk", "lawsuit", "decline", "sell", "negative", "warn", "warning",
}

HF_MODEL_ID = "ProsusAI/finbert"
HF_ENDPOINT = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"

st.set_page_config(page_title="ML Stock Tracker", layout="wide", initial_sidebar_state="expanded")

OWID_STYLE = """
<style>
:root {
    --owid-navy: #08306b;
    --owid-blue: #1f5aa6;
    --owid-accent: #d73a49;
    --owid-bg: #f5f6f9;
    --owid-panel: #ffffff;
    --owid-border: #d9dee8;
    --owid-text: #1f2937;
    --owid-muted: #6b7280;
    --owid-pos: #1f9d68;
    --owid-neg: #c13737;
}
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: var(--owid-bg) !important;
    color: var(--owid-text);
    font-family: Georgia, "Times New Roman", serif;
}
[data-testid="stSidebar"] {
    background: #eef2f8;
    border-right: 1px solid var(--owid-border);
}
h1, h2, h3 {
    font-family: Georgia, "Times New Roman", serif;
    letter-spacing: -0.01em;
}
.owid-topbar {
    background: var(--owid-navy);
    color: #fff;
    padding: 0.55rem 1rem;
    border-bottom: 3px solid var(--owid-accent);
    margin: -2.8rem -1rem 0.8rem -1rem;
}
.owid-hero {
    background: linear-gradient(180deg, #f2f5fb 0%, #ffffff 100%);
    border: 1px solid var(--owid-border);
    padding: 1rem 1.2rem;
    margin-bottom: 0.9rem;
}
.owid-subnav {
    border-bottom: 1px solid var(--owid-border);
    padding-bottom: 0.35rem;
    margin-top: 0.4rem;
    color: var(--owid-muted);
    font-size: 0.9rem;
}
.owid-panel {
    background: var(--owid-panel);
    border: 1px solid var(--owid-border);
    padding: 0.8rem;
    margin-bottom: 0.8rem;
}
.owid-metric {
    background: #fff;
    border: 1px solid var(--owid-border);
    padding: 0.65rem;
    text-align: center;
}
.owid-label {
    color: var(--owid-muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.owid-value {
    font-size: 1.4rem;
    margin-top: 0.2rem;
}
.pos { color: var(--owid-pos); }
.neg { color: var(--owid-neg); }
.neu { color: var(--owid-muted); }
.stButton button {
    border-radius: 2px !important;
    border: 1px solid #b8c2d8 !important;
}
</style>
"""


def inject_styles() -> None:
    st.markdown(OWID_STYLE, unsafe_allow_html=True)


def normalize_watch_symbol(raw: str) -> str:
    code = raw.strip().upper()
    if not code:
        return ""
    if code == "BRK.B.US":
        return "BRK-B"
    if code.endswith("USD.CC"):
        return f"{code[:3]}-USD"
    if code.endswith(".US"):
        return code[:-3]
    if code.endswith(".HK"):
        hk = code.split(".")[0].lstrip("0") or "0"
        return f"{hk}.HK"
    return code


def build_default_watchlist() -> list[str]:
    normalized = [normalize_watch_symbol(s) for s in RAW_WATCHLIST]
    cleaned: list[str] = []
    for symbol in normalized:
        if symbol and symbol not in cleaned:
            cleaned.append(symbol)
    return cleaned


def init_state() -> None:
    defaults = {
        "watchlist": build_default_watchlist(),
        "price_rows": [],
        "analysis_rows": [],
        "news_rows": [],
        "fetch_logs": [],
        "last_refreshed": None,
        "trend_df": pd.DataFrame(columns=["Date", "Avg Sentiment"]),
        "volume_df": pd.DataFrame(columns=["Date", "Positive", "Negative"]),
        "hf_model_status": "Not checked",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def log_event(message: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.fetch_logs.append(f"[{ts}] {message}")
    if len(st.session_state.fetch_logs) > 200:
        st.session_state.fetch_logs = st.session_state.fetch_logs[-200:]


def safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
        return None if pd.isna(parsed) else parsed
    except (TypeError, ValueError):
        return None


def format_big_number(value: float | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    return f"{value:,.0f}"


def yahoo_link(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{urllib.parse.quote(ticker)}"


def tokenized(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def simple_sentiment_score(text: str) -> float:
    words = tokenized(text)
    if not words:
        return 0.0
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def _hf_inference_call(text: str) -> tuple[str, float] | None:
    token = os.getenv("HF_TOKEN")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = json.dumps({"inputs": text, "options": {"wait_for_model": True}}).encode("utf-8")
    req = urllib.request.Request(HF_ENDPOINT, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log_event(f"HF inference unavailable, fallback used ({exc}).")
        return None

    if isinstance(data, dict) and data.get("error"):
        log_event(f"HF API error: {data['error']}")
        return None

    # Typical response: [[{"label":"positive","score":0.99}, ...]]
    if isinstance(data, list) and data:
        items = data[0] if isinstance(data[0], list) else data
        best = max(items, key=lambda x: float(x.get("score", 0)))
        label = str(best.get("label", "neutral")).lower()
        score = float(best.get("score", 0))
        if label == "positive":
            signed_score = score
        elif label == "negative":
            signed_score = -score
        else:
            signed_score = 0.0
        return label.capitalize(), signed_score

    return None


def fetch_stock_snapshots_batch(tickers: list[str]) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    failures: list[str] = []
    if not tickers:
        return rows, failures

    log_event(f"Fetching {len(tickers)} watchlist symbols...")
    for ticker in tickers:
        try:
            hist = yf.download(ticker, period="1mo", interval="1d", auto_adjust=False, progress=False, threads=False)
            if hist.empty or "Close" not in hist.columns:
                failures.append(f"{ticker}: no market data")
                continue
            valid = hist.dropna(subset=["Close"])
            if valid.empty:
                failures.append(f"{ticker}: empty close series")
                continue
            cur = valid.iloc[-1]
            prev_close = safe_float(valid.iloc[-2]["Close"]) if len(valid) > 1 else None
            close_val = safe_float(cur.get("Close"))
            low_val = safe_float(cur.get("Low"))
            high_val = safe_float(cur.get("High"))
            open_val = safe_float(cur.get("Open"))
            volume = safe_float(cur.get("Volume"))

            pct_change = None
            if close_val is not None and prev_close not in (None, 0):
                pct_change = ((close_val - prev_close) / prev_close) * 100

            rows.append({
                "Ticker": f"<a href='{yahoo_link(ticker)}' target='_blank'>{ticker}</a>",
                "Current": f"${close_val:,.2f}" if close_val is not None else "-",
                "Change %": f"{pct_change:+.2f}%" if pct_change is not None else "-",
                "Low": f"${low_val:,.2f}" if low_val is not None else "-",
                "High": f"${high_val:,.2f}" if high_val is not None else "-",
                "Open": f"${open_val:,.2f}" if open_val is not None else "-",
                "Volume": format_big_number(volume),
            })
        except Exception as exc:
            failures.append(f"{ticker}: {exc}")
    log_event(f"Price load complete: {len(rows)} success, {len(failures)} failed")
    return rows, failures


def run_ml_analysis(ticker: str) -> dict:
    hist = yf.download(ticker, period="6mo", interval="1d", auto_adjust=True, progress=False, threads=False)
    if hist.empty or len(hist) < 30 or "Close" not in hist.columns:
        raise ValueError("not enough history")

    closes = hist["Close"].dropna()
    returns = closes.pct_change().dropna()
    x = np.arange(len(closes))
    slope = float(np.polyfit(x, np.asarray(closes, dtype=float), 1)[0])
    momentum = ((closes.iloc[-1] / closes.iloc[-20]) - 1) * 100 if len(closes) >= 20 else np.nan
    volatility = float(returns.std() * np.sqrt(252)) if not returns.empty else np.nan

    if pd.notna(momentum) and pd.notna(volatility):
        if momentum > 3 and slope > 0 and volatility < 0.45:
            signal, confidence = "Buy", "High"
        elif momentum < -3 or slope < 0:
            signal, confidence = "Sell", "Medium"
        else:
            signal, confidence = "Hold", "Medium"
    else:
        signal, confidence = "Hold", "Low"

    return {
        "Ticker": f"<a href='{yahoo_link(ticker)}' target='_blank'>{ticker}</a>",
        "Signal": signal,
        "Confidence": confidence,
        "Momentum 20d": f"{momentum:+.2f}%" if pd.notna(momentum) else "-",
        "Volatility": f"{volatility:.2f}" if pd.notna(volatility) else "-",
    }


def fetch_news_sentiment(ticker: str) -> tuple[list[dict], pd.DataFrame, pd.DataFrame]:
    stock = yf.Ticker(ticker)
    news_items = stock.news or []
    if not news_items:
        return [], pd.DataFrame(columns=["Date", "Avg Sentiment"]), pd.DataFrame(columns=["Date", "Positive", "Negative"])

    rows = []
    hf_ok = False
    for item in news_items[:30]:
        title = item.get("title") or ""
        summary = item.get("summary") or ""
        publisher = item.get("publisher") or "Unknown"
        ts = item.get("providerPublishTime")
        date_val = datetime.fromtimestamp(ts, tz=timezone.utc).date() if isinstance(ts, (int, float)) else datetime.now(timezone.utc).date()
        text = f"{title}. {summary}".strip()

        hf_res = _hf_inference_call(text[:900])
        if hf_res:
            sentiment, score = hf_res
            hf_ok = True
        else:
            score = simple_sentiment_score(text)
            sentiment = "Positive" if score > 0.15 else ("Negative" if score < -0.15 else "Neutral")

        rows.append({
            "Date": str(date_val),
            "Publisher": publisher,
            "Headline": title or "(No title)",
            "Sentiment": sentiment,
            "Score": round(score, 3),
        })

    st.session_state.hf_model_status = f"Active ({HF_MODEL_ID})" if hf_ok else "Fallback lexicon"

    news_df = pd.DataFrame(rows)
    trend_df = news_df.groupby("Date", as_index=False).agg(**{"Avg Sentiment": ("Score", "mean")}).sort_values("Date")

    volume_df = pd.DataFrame(
        news_df[news_df["Sentiment"].isin(["Positive", "Negative"])]
        .groupby(["Date", "Sentiment"], as_index=False)
        .size()
        .pivot(index="Date", columns="Sentiment", values="size")
        .fillna(0)
        .reset_index()
        .sort_values("Date")
    )
    if "Positive" not in volume_df.columns:
        volume_df["Positive"] = 0
    if "Negative" not in volume_df.columns:
        volume_df["Negative"] = 0

    return rows, trend_df, volume_df[["Date", "Positive", "Negative"]]


def render_table_html(rows: list[dict]) -> str:
    if not rows:
        return "<div class='owid-panel'>No rows to display.</div>"
    df = pd.DataFrame(rows)
    html = "<table style='width:100%;border-collapse:collapse;font-size:0.9rem'>"
    html += "<thead><tr>"
    for col in df.columns:
        html += f"<th style='text-align:left;padding:0.45rem;border-bottom:1px solid #d9dee8;color:#6b7280'>{col}</th>"
    html += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        html += "<tr>"
        for col in df.columns:
            val = str(row[col])
            cell_style = "padding:0.45rem;border-bottom:1px solid #edf0f6;"
            if col in ("Change %", "Score"):
                if val.startswith("+"):
                    cell_style += "color:#1f9d68;"
                elif val.startswith("-"):
                    cell_style += "color:#c13737;"
            html += f"<td style='{cell_style}'>{val}</td>"
        html += "</tr>"
    html += "</tbody></table>"
    return html


def render_header() -> None:
    st.markdown(
        """
        <div class="owid-topbar">
            <strong>Our World in Data style</strong> | Stock Tracker Dashboard
        </div>
        <div class="owid-hero">
            <h2 style="margin:0;color:#08306b;">Market dashboard</h2>
            <p style="margin:0.35rem 0 0.35rem 0;color:#4b5563;">Live watchlist quotes, rule-based ML signals, and Hugging Face sentiment.</p>
            <div class="owid-subnav">Explore the data | Charts | Table | Analysis</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[bool, bool, bool, str]:
    with st.sidebar:
        st.markdown("### Controls")
        selected_ticker = st.selectbox("Ticker for analysis", options=st.session_state.watchlist, index=0)

        add_raw = st.text_input("Add watchlist symbols", placeholder="AAPL, BRK.B.US, ETHUSD.CC")
        if st.button("Add symbols", use_container_width=True):
            items = [normalize_watch_symbol(x) for x in add_raw.split(",")]
            items = [x for x in items if x]
            for item in items:
                if item not in st.session_state.watchlist:
                    st.session_state.watchlist.append(item)
                    log_event(f"Added {item}")

        fetch_clicked = st.button("Obtain Stock Price & yfinance Info", use_container_width=True)
        analysis_clicked = st.button("Start Analysis / ML", use_container_width=True)
        news_clicked = st.button("Load News Sentiment", use_container_width=True)

        st.markdown("---")
        st.caption(f"HF sentiment model: {HF_MODEL_ID}")
        st.caption(f"Model status: {st.session_state.hf_model_status}")

    return fetch_clicked, analysis_clicked, news_clicked, selected_ticker


def render_main() -> None:
    tab1, tab2, tab3 = st.tabs(["Table", "Chart", "Statistics"])

    with tab1:
        st.markdown("<div class='owid-panel'><h3 style='margin-top:0'>Watchlist table</h3>", unsafe_allow_html=True)
        st.markdown(render_table_html(st.session_state.price_rows), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.analysis_rows:
            st.markdown("<div class='owid-panel'><h3 style='margin-top:0'>ML output</h3>", unsafe_allow_html=True)
            st.markdown(render_table_html(st.session_state.analysis_rows), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.news_rows:
            st.markdown("<div class='owid-panel'><h3 style='margin-top:0'>News sentiment</h3>", unsafe_allow_html=True)
            st.markdown(render_table_html(st.session_state.news_rows), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        if st.session_state.price_rows:
            df = pd.DataFrame(st.session_state.price_rows)
            df["TickerPlain"] = df["Ticker"].str.replace(r"<[^>]+>", "", regex=True)
            df["CurrentFloat"] = pd.to_numeric(df["Current"].str.replace("$", "", regex=False).str.replace(",", "", regex=False), errors="coerce")
            chart_df = df[["TickerPlain", "CurrentFloat"]].dropna()
            st.bar_chart(chart_df.set_index("TickerPlain"), height=420)
        else:
            st.info("Fetch prices first to display chart.")

        if not st.session_state.trend_df.empty:
            st.line_chart(st.session_state.trend_df.set_index("Date"), height=260)

    with tab3:
        if st.session_state.price_rows:
            df = pd.DataFrame(st.session_state.price_rows)
            pct = pd.to_numeric(df["Change %"].str.replace("%", "", regex=False), errors="coerce")
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='owid-metric'><div class='owid-label'>Tickers Loaded</div><div class='owid-value'>{len(df)}</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='owid-metric'><div class='owid-label'>Avg Change</div><div class='owid-value'>{pct.mean():+.2f}%</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='owid-metric'><div class='owid-label'>Best Move</div><div class='owid-value pos'>{pct.max():+.2f}%</div></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='owid-metric'><div class='owid-label'>Worst Move</div><div class='owid-value neg'>{pct.min():+.2f}%</div></div>", unsafe_allow_html=True)
        else:
            st.info("No statistics yet. Load prices first.")

        if st.session_state.fetch_logs:
            st.markdown("### Activity log")
            st.code("\n".join(st.session_state.fetch_logs[-70:]))


inject_styles()
init_state()
render_header()
fetch_clicked, analysis_clicked, news_clicked, selected_ticker = render_sidebar()

if not st.session_state.price_rows:
    with st.spinner("Loading initial watchlist prices..."):
        rows, failures = fetch_stock_snapshots_batch(st.session_state.watchlist)
        st.session_state.price_rows = rows
        st.session_state.last_refreshed = datetime.now(timezone.utc)
        if failures:
            log_event(f"Initial failures: {len(failures)}")

if fetch_clicked:
    with st.spinner("Fetching latest prices..."):
        rows, failures = fetch_stock_snapshots_batch(st.session_state.watchlist)
        st.session_state.price_rows = rows
        st.session_state.last_refreshed = datetime.now(timezone.utc)
    if rows:
        st.success(f"Loaded {len(rows)} symbols.")
    if failures:
        st.warning("Some symbols failed: " + " | ".join(failures[:8]))

if analysis_clicked:
    with st.spinner("Running ML analysis..."):
        output = []
        failed = []
        for ticker in st.session_state.watchlist:
            try:
                output.append(run_ml_analysis(ticker))
            except Exception as exc:
                failed.append(f"{ticker}: {exc}")
        st.session_state.analysis_rows = output
    st.success(f"ML completed for {len(output)} symbols.")
    if failed:
        st.warning("Some analyses failed: " + " | ".join(failed[:8]))

if news_clicked:
    with st.spinner(f"Analyzing latest news for {selected_ticker}..."):
        try:
            rows, trend_df, volume_df = fetch_news_sentiment(selected_ticker)
            st.session_state.news_rows = rows
            st.session_state.trend_df = trend_df
            st.session_state.volume_df = volume_df
            st.success(f"Loaded {len(rows)} news items for {selected_ticker}.")
        except Exception as exc:
            st.error(f"News sentiment failed: {exc}")

render_main()
