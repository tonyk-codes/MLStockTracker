"""
ML Stock Tracker - Analysis Pipeline
Fetches stock data, runs ML strategies, outputs JSON for GitHub Pages dashboard.

Strategies:
1. MA Golden Cross (50/200 SMA)
2. News Sentiment Analysis (FinBERT via HF API + lexicon fallback)
3. FinRL-inspired signals (momentum, volatility, trend, mean-reversion)
4. Stock Correlation Analysis
"""

import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
RAW_WATCHLIST = [
    "AMDL.US", "GGLL.US", "MSFU.US", "QNCX.US", "BRK.B.US", "AMD.US",
    "OXY.US", "AEG.US", "GOOGL.US", "BABA.US", "BABX.US", "TSLA.US",
    "SQQQ.US", "HIMZ.US", "LULG.US", "AMZU.US", "NFXL.US", "BRKU.US",
    "PYPG.US", "ETHUSD.CC", "AGQ.US", "GALDY.US", "BTCUSD.CC", "INTW.US",
    "KO.US", "NVDA.US", "01881.HK", "AAPU.US", "GOOG.US", "MSFT.US",
    "SCHD.US", "VT.US", "GME.US", "SSO.US", "LCDL.US", "TSLL.US",
    "METU.US", "META.US", "VUG.US", "NVDL.US", "SOXS.US", "UNHG.US",
    "UNH.US", "LULU.US", "AAPL.US", "NKE.US", "QQQ.US", "VOO.US",
    "VTI.US", "TQQQ.US", "LCID.US",
]

POSITIVE_WORDS = {
    "beat", "beats", "growth", "upgrade", "surge", "gain", "bullish", "strong",
    "record", "profit", "outperform", "buy", "rise", "improve", "positive",
    "soar", "rally", "boost", "exceed", "optimistic", "breakout", "momentum",
}
NEGATIVE_WORDS = {
    "miss", "cuts", "downgrade", "drop", "fall", "bearish", "weak", "loss",
    "risk", "lawsuit", "decline", "sell", "negative", "warn", "warning",
    "crash", "plunge", "slump", "recession", "default", "bankruptcy", "layoff",
}

HF_MODEL_ID = "ProsusAI/finbert"
HF_ENDPOINT = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def normalize_symbol(raw: str) -> str:
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


def build_watchlist() -> list[str]:
    seen = set()
    result = []
    for raw in RAW_WATCHLIST:
        sym = normalize_symbol(raw)
        if sym and sym not in seen:
            seen.add(sym)
            result.append(sym)
    return result


def safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def fmt_pct(val: float | None) -> str | None:
    return f"{val:+.2f}%" if val is not None else None


def fmt_price(val: float | None) -> str | None:
    return f"{val:,.2f}" if val is not None else None


def fmt_big(val: float | None) -> str | None:
    if val is None:
        return None
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.2f}M"
    return f"{val:,.0f}"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# SENTIMENT HELPERS
# ---------------------------------------------------------------------------
def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower())


def lexicon_sentiment(text: str) -> tuple[str, float]:
    words = tokenize(text)
    if not words:
        return "Neutral", 0.0
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    if pos + neg == 0:
        return "Neutral", 0.0
    score = (pos - neg) / (pos + neg)
    label = "Positive" if score > 0.15 else ("Negative" if score < -0.15 else "Neutral")
    return label, round(score, 4)


def hf_sentiment(text: str) -> tuple[str, float] | None:
    token = os.getenv("HF_TOKEN")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = json.dumps({"inputs": text[:512], "options": {"wait_for_model": True}}).encode()
    req = urllib.request.Request(HF_ENDPOINT, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    if isinstance(data, dict) and data.get("error"):
        return None
    if isinstance(data, list) and data:
        items = data[0] if isinstance(data[0], list) else data
        best = max(items, key=lambda x: float(x.get("score", 0)))
        label = str(best.get("label", "neutral")).lower()
        score = float(best.get("score", 0))
        signed = score if label == "positive" else (-score if label == "negative" else 0.0)
        return label.capitalize(), round(signed, 4)
    return None


# ---------------------------------------------------------------------------
# STRATEGY 1: PRICE SNAPSHOT + BASICS
# ---------------------------------------------------------------------------
def fetch_prices(tickers: list[str]) -> list[dict]:
    log(f"Fetching prices for {len(tickers)} symbols...")
    rows = []
    for ticker in tickers:
        try:
            hist = yf.download(
                ticker, period="1mo", interval="1d",
                auto_adjust=False, progress=False, threads=False
            )
            if hist.empty or "Close" not in hist.columns:
                log(f"  {ticker}: no data")
                continue
            valid = hist.dropna(subset=["Close"])
            if valid.empty:
                continue
            cur = valid.iloc[-1]
            prev = safe_float(valid.iloc[-2]["Close"]) if len(valid) > 1 else None
            close = safe_float(cur.get("Close"))
            pct = ((close - prev) / prev * 100) if close and prev else None
            rows.append({
                "ticker": ticker,
                "price": safe_float(cur.get("Close")),
                "open": safe_float(cur.get("Open")),
                "high": safe_float(cur.get("High")),
                "low": safe_float(cur.get("Low")),
                "volume": safe_float(cur.get("Volume")),
                "change_pct": round(pct, 2) if pct is not None else None,
                "prev_close": prev,
            })
        except Exception as e:
            log(f"  {ticker}: error {e}")
    log(f"  Prices done: {len(rows)} loaded")
    return rows


# ---------------------------------------------------------------------------
# STRATEGY 2: MA GOLDEN CROSS / DEATH CROSS (50/200 SMA)
# ---------------------------------------------------------------------------
def ma_cross_analysis(tickers: list[str]) -> list[dict]:
    log("Running MA Golden/Death Cross analysis...")
    results = []
    for ticker in tickers:
        try:
            hist = yf.download(
                ticker, period="1y", interval="1d",
                auto_adjust=True, progress=False, threads=False
            )
            if hist.empty or len(hist) < 50 or "Close" not in hist.columns:
                continue
            closes = hist["Close"].dropna()
            sma50 = closes.rolling(50).mean()
            sma200 = closes.rolling(200).mean() if len(closes) >= 200 else pd.Series(dtype=float)

            current_sma50 = safe_float(sma50.iloc[-1])
            current_sma200 = safe_float(sma200.iloc[-1]) if len(sma200) > 0 and not sma200.isna().all() else None
            prev_sma50 = safe_float(sma50.iloc[-2]) if len(sma50) > 1 else None
            prev_sma200 = safe_float(sma200.iloc[-2]) if (len(sma200) > 1 and not sma200.isna().all()) else None

            signal = "Insufficient Data"
            if current_sma50 is not None and current_sma200 is not None:
                if prev_sma50 is not None and prev_sma200 is not None:
                    if prev_sma50 <= prev_sma200 and current_sma50 > current_sma200:
                        signal = "Golden Cross"
                    elif prev_sma50 >= prev_sma200 and current_sma50 < current_sma200:
                        signal = "Death Cross"
                    elif current_sma50 > current_sma200:
                        signal = "Bullish (50 > 200)"
                    else:
                        signal = "Bearish (50 < 200)"

            # Build SMA history for chart (last 60 days)
            sma_history = []
            start_idx = max(0, len(closes) - 60)
            dates = closes.index[start_idx:]
            for i, dt in enumerate(dates):
                idx = start_idx + i
                entry = {"date": dt.strftime("%Y-%m-%d")}
                entry["close"] = safe_float(closes.iloc[idx])
                if idx < len(sma50):
                    entry["sma50"] = safe_float(sma50.iloc[idx])
                if idx < len(sma200) and not sma200.isna().all():
                    entry["sma200"] = safe_float(sma200.iloc[idx])
                sma_history.append(entry)

            results.append({
                "ticker": ticker,
                "signal": signal,
                "sma50": current_sma50,
                "sma200": current_sma200,
                "sma_history": sma_history,
            })
        except Exception as e:
            log(f"  MA {ticker}: {e}")
    log(f"  MA analysis done: {len(results)} stocks")
    return results


# ---------------------------------------------------------------------------
# STRATEGY 3: SENTIMENT ANALYSIS (NEWS)
# ---------------------------------------------------------------------------
def sentiment_analysis(tickers: list[str]) -> list[dict]:
    log("Running sentiment analysis...")
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            news_items = stock.news or []
            if not news_items:
                results.append({
                    "ticker": ticker,
                    "avg_score": 0.0,
                    "label": "No News",
                    "news_count": 0,
                    "headlines": [],
                })
                continue

            headlines = []
            scores = []
            for item in news_items[:20]:
                title = item.get("title") or ""
                summary = item.get("summary") or ""
                publisher = item.get("publisher") or "Unknown"
                ts = item.get("providerPublishTime")
                date_str = (
                    datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                    if isinstance(ts, (int, float))
                    else datetime.now(timezone.utc).strftime("%Y-%m-%d")
                )
                text = f"{title}. {summary}".strip()
                hf_res = hf_sentiment(text)
                if hf_res:
                    label, score = hf_res
                else:
                    label, score = lexicon_sentiment(text)
                scores.append(score)
                headlines.append({
                    "date": date_str,
                    "title": title,
                    "publisher": publisher,
                    "sentiment": label,
                    "score": score,
                })

            avg = round(sum(scores) / len(scores), 4) if scores else 0.0
            overall = "Positive" if avg > 0.1 else ("Negative" if avg < -0.1 else "Neutral")
            results.append({
                "ticker": ticker,
                "avg_score": avg,
                "label": overall,
                "news_count": len(headlines),
                "headlines": headlines,
            })
        except Exception as e:
            log(f"  Sentiment {ticker}: {e}")
    log(f"  Sentiment done: {len(results)} stocks")
    return results


# ---------------------------------------------------------------------------
# STRATEGY 4: FinRL-INSPIRED SIGNALS
# ---------------------------------------------------------------------------
def finrl_signals(tickers: list[str]) -> list[dict]:
    log("Running FinRL-inspired strategy analysis...")
    results = []
    for ticker in tickers:
        try:
            hist = yf.download(
                ticker, period="6mo", interval="1d",
                auto_adjust=True, progress=False, threads=False
            )
            if hist.empty or len(hist) < 30 or "Close" not in hist.columns:
                continue
            closes = hist["Close"].dropna()
            returns = closes.pct_change().dropna()

            # Features
            x = np.arange(len(closes))
            slope = float(np.polyfit(x, np.asarray(closes, dtype=float), 1)[0])
            momentum_20d = float((closes.iloc[-1] / closes.iloc[-20] - 1) * 100) if len(closes) >= 20 else None
            momentum_5d = float((closes.iloc[-1] / closes.iloc[-5] - 1) * 100) if len(closes) >= 5 else None
            volatility = float(returns.std() * np.sqrt(252))
            avg_volume = safe_float(hist["Volume"].tail(20).mean()) if "Volume" in hist.columns else None

            # RSI (14-day)
            delta = closes.diff()
            gain = delta.where(delta > 0, 0.0).rolling(14).mean()
            loss_ = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
            rs = gain / loss_
            rsi = 100 - (100 / (1 + rs))
            current_rsi = safe_float(rsi.iloc[-1])

            # Bollinger Bands
            sma20 = closes.rolling(20).mean()
            std20 = closes.rolling(20).std()
            upper_bb = sma20 + 2 * std20
            lower_bb = sma20 - 2 * std20
            current_price = safe_float(closes.iloc[-1])
            bb_upper = safe_float(upper_bb.iloc[-1])
            bb_lower = safe_float(lower_bb.iloc[-1])
            bb_position = None
            if current_price and bb_upper and bb_lower and (bb_upper - bb_lower) > 0:
                bb_position = round((current_price - bb_lower) / (bb_upper - bb_lower), 3)

            # MACD
            ema12 = closes.ewm(span=12, adjust=False).mean()
            ema26 = closes.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line
            macd_val = safe_float(macd_hist.iloc[-1])

            # Sharpe ratio (annualized, risk-free = 0)
            sharpe = float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0.0

            # Composite Score & Signal
            score = 0.0
            reasons = []

            if momentum_20d is not None:
                if momentum_20d > 5:
                    score += 2
                    reasons.append("Strong 20d momentum")
                elif momentum_20d > 0:
                    score += 1
                    reasons.append("Positive 20d momentum")
                elif momentum_20d < -5:
                    score -= 2
                    reasons.append("Weak 20d momentum")
                else:
                    score -= 1

            if slope > 0:
                score += 1
                reasons.append("Upward trend")
            else:
                score -= 1
                reasons.append("Downward trend")

            if volatility < 0.3:
                score += 1
                reasons.append("Low volatility")
            elif volatility > 0.6:
                score -= 1
                reasons.append("High volatility")

            if current_rsi is not None:
                if current_rsi < 30:
                    score += 1.5
                    reasons.append("Oversold (RSI)")
                elif current_rsi > 70:
                    score -= 1.5
                    reasons.append("Overbought (RSI)")

            if bb_position is not None:
                if bb_position < 0.2:
                    score += 1
                    reasons.append("Near lower BB")
                elif bb_position > 0.8:
                    score -= 1
                    reasons.append("Near upper BB")

            if macd_val is not None:
                if macd_val > 0:
                    score += 0.5
                    reasons.append("MACD bullish")
                else:
                    score -= 0.5
                    reasons.append("MACD bearish")

            if sharpe > 1:
                score += 1
                reasons.append(f"Good Sharpe ({sharpe:.2f})")
            elif sharpe < -0.5:
                score -= 1

            if score >= 3:
                signal = "Strong Buy"
                confidence = "High"
            elif score >= 1:
                signal = "Buy"
                confidence = "Medium"
            elif score <= -3:
                signal = "Strong Sell"
                confidence = "High"
            elif score <= -1:
                signal = "Sell"
                confidence = "Medium"
            else:
                signal = "Hold"
                confidence = "Low"

            results.append({
                "ticker": ticker,
                "signal": signal,
                "confidence": confidence,
                "composite_score": round(score, 2),
                "momentum_20d": round(momentum_20d, 2) if momentum_20d is not None else None,
                "momentum_5d": round(momentum_5d, 2) if momentum_5d is not None else None,
                "volatility": round(volatility, 4),
                "rsi": round(current_rsi, 2) if current_rsi is not None else None,
                "macd": round(macd_val, 4) if macd_val is not None else None,
                "bb_position": bb_position,
                "sharpe": round(sharpe, 3),
                "slope": round(slope, 4),
                "avg_volume": avg_volume,
                "reasons": reasons[:5],
            })
        except Exception as e:
            log(f"  FinRL {ticker}: {e}")
    log(f"  FinRL analysis done: {len(results)} stocks")
    return results


# ---------------------------------------------------------------------------
# STRATEGY 5: CORRELATION ANALYSIS
# ---------------------------------------------------------------------------
def correlation_analysis(tickers: list[str]) -> dict:
    log("Running correlation analysis...")
    # Download 3 months of daily closes for all tickers
    valid_tickers = []
    all_closes = {}
    for ticker in tickers:
        try:
            hist = yf.download(
                ticker, period="3mo", interval="1d",
                auto_adjust=True, progress=False, threads=False
            )
            if hist.empty or "Close" not in hist.columns:
                continue
            closes = hist["Close"].dropna()
            if len(closes) < 20:
                continue
            all_closes[ticker] = closes
            valid_tickers.append(ticker)
        except Exception:
            pass

    if len(valid_tickers) < 2:
        log("  Not enough stocks for correlation")
        return {"tickers": [], "matrix": [], "top_pairs": []}

    # Build aligned dataframe
    df = pd.DataFrame(all_closes)
    df = df.dropna(axis=0, how="any")
    returns_df = df.pct_change().dropna()

    if len(returns_df) < 10:
        return {"tickers": valid_tickers, "matrix": [], "top_pairs": []}

    corr = returns_df.corr()

    # Build matrix as list of lists
    matrix = []
    for t1 in valid_tickers:
        row = []
        for t2 in valid_tickers:
            if t1 in corr.columns and t2 in corr.columns:
                val = safe_float(corr.loc[t1, t2])
                row.append(round(val, 3) if val is not None else None)
            else:
                row.append(None)
        matrix.append(row)

    # Top correlated / anti-correlated pairs
    pairs = []
    for i, t1 in enumerate(valid_tickers):
        for j, t2 in enumerate(valid_tickers):
            if j <= i:
                continue
            if t1 in corr.columns and t2 in corr.columns:
                val = safe_float(corr.loc[t1, t2])
                if val is not None:
                    pairs.append({"pair": f"{t1} / {t2}", "correlation": round(val, 3)})

    pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    top_positive = [p for p in pairs if p["correlation"] > 0.5][:15]
    top_negative = [p for p in pairs if p["correlation"] < -0.3][:15]

    log(f"  Correlation done: {len(valid_tickers)} stocks, {len(pairs)} pairs")
    return {
        "tickers": valid_tickers,
        "matrix": matrix,
        "top_positive": top_positive,
        "top_negative": top_negative,
    }


# ---------------------------------------------------------------------------
# COMBINED SIGNAL
# ---------------------------------------------------------------------------
def compute_combined_signals(
    prices: list[dict],
    ma_results: list[dict],
    sentiment_results: list[dict],
    finrl_results: list[dict],
) -> list[dict]:
    log("Computing combined signals...")
    ma_map = {r["ticker"]: r for r in ma_results}
    sent_map = {r["ticker"]: r for r in sentiment_results}
    finrl_map = {r["ticker"]: r for r in finrl_results}

    combined = []
    for p in prices:
        ticker = p["ticker"]
        score = 0.0

        # MA signal
        ma = ma_map.get(ticker)
        if ma:
            sig = ma.get("signal", "")
            if "Golden Cross" in sig:
                score += 3
            elif "Bullish" in sig:
                score += 1
            elif "Death Cross" in sig:
                score -= 3
            elif "Bearish" in sig:
                score -= 1

        # Sentiment
        sent = sent_map.get(ticker)
        if sent:
            avg = sent.get("avg_score", 0)
            score += avg * 3  # scale sentiment contribution

        # FinRL
        finrl = finrl_map.get(ticker)
        if finrl:
            score += finrl.get("composite_score", 0) * 0.5

        if score >= 3:
            signal = "Strong Buy"
        elif score >= 1:
            signal = "Buy"
        elif score <= -3:
            signal = "Strong Sell"
        elif score <= -1:
            signal = "Sell"
        else:
            signal = "Hold"

        combined.append({
            "ticker": ticker,
            "combined_score": round(score, 2),
            "combined_signal": signal,
            "ma_signal": ma["signal"] if ma else "N/A",
            "sentiment_label": sent["label"] if sent else "N/A",
            "sentiment_score": sent["avg_score"] if sent else 0,
            "finrl_signal": finrl["signal"] if finrl else "N/A",
            "finrl_score": finrl["composite_score"] if finrl else 0,
            "price": p.get("price"),
            "change_pct": p.get("change_pct"),
        })

    combined.sort(key=lambda x: x["combined_score"], reverse=True)
    log(f"  Combined signals done: {len(combined)} stocks")
    return combined


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    log("=" * 60)
    log("ML Stock Tracker - Analysis Pipeline")
    log("=" * 60)

    tickers = build_watchlist()
    log(f"Watchlist: {len(tickers)} symbols")

    # Run all strategies
    prices = fetch_prices(tickers)
    ma_results = ma_cross_analysis(tickers)
    sentiment_results = sentiment_analysis(tickers)
    finrl_results = finrl_signals(tickers)
    correlation = correlation_analysis(tickers)
    combined = compute_combined_signals(prices, ma_results, sentiment_results, finrl_results)

    # Build output
    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "watchlist": tickers,
        "prices": prices,
        "ma_cross": ma_results,
        "sentiment": sentiment_results,
        "finrl": finrl_results,
        "correlation": correlation,
        "combined": combined,
    }

    # Strip SMA history from ma_cross for the main JSON to keep size manageable
    # (sma_history is embedded per-stock for chart rendering)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "analysis.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)
    log(f"Output written to {out_path} ({out_path.stat().st_size:,} bytes)")
    log("Done!")


if __name__ == "__main__":
    main()
