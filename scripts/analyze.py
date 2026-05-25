"""
Machine Learning Signal Platform — Analysis Pipeline

Signal logic (from trading algorithm):

  Symbol Classification:
    TL = (ret60d >= +40%  OR  ret120d >= +80%)  AND  price >= 52w_high * 0.80
    N  = all others

  BUY_TL (ALL conditions required):
    price > MA50
    MA20 >= MA50
    MA50 slope > 0
    MA20 * 0.92 <= price <= MA20 * 1.02
    35 <= RSI14 <= 65
    QQQ 5d_ret > -5%

  BUY_N (ALL conditions required):
    price > MA20
    price > MA50
    MA20 * 0.93 <= price <= MA20 * 1.00
    40 <= RSI14 <= 60
    QQQ 5d_ret > 0

  SELL_TL (ANY triggers, checked before BUY):
    price < MA20 * 0.97   (broke below MA20)
    price < peak60d * 0.82  (18% drawdown from 60-day peak)

  SELL_N (ANY triggers, checked before BUY):
    price < MA50
    price < peak60d * 0.90  (10% drawdown from 60-day peak)

  Note: unrealized PnL conditions are evaluated in the frontend
  when user uploads a portfolio file with cost basis.

Correlation:
  60-day daily returns, excludes ETF-parent pairs and same-company tickers.
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# Watchlist (US equities only, from Stock-List.csv)
# BRK.B.US normalized to BRK-B for yfinance
# ---------------------------------------------------------------------------
TICKERS = [
    "AEG", "AMD", "AMDL", "BABA", "BABX", "BRK-B", "GGLL", "MSFU",
    "OXY", "QNCX", "TSLA", "AAPL", "AAPU", "AGQ", "AMZU", "BRKU",
    "GALDY", "GME", "GOOG", "HIMZ", "INTW", "KO", "LCDL", "LCID",
    "LULG", "LULU", "META", "METU", "MSFT", "NFXL", "NKE", "NVDA",
    "NVDL", "PMRTY", "PYPG", "QQQ", "SCHD", "SOXS", "SQQQ", "SSO",
    "TQQQ", "TSLL", "UNH", "UNHG", "VOO", "VT", "VTI", "VUG",
    "GOOGL", "TSM",
]

TICKER_NAMES = {
    "AEG": "Aegon N.V.", "AMD": "Adv. Micro Devices",
    "AMDL": "2x AMD (GraniteShares)", "BABA": "Alibaba Group",
    "BABX": "2x BABA (GraniteShares)", "BRK-B": "Berkshire Hathaway B",
    "GGLL": "2x GOOGL (Direxion)", "MSFU": "2x MSFT (Direxion)",
    "OXY": "Occidental Petroleum", "QNCX": "Quince Therapeutics",
    "TSLA": "Tesla Inc.", "AAPL": "Apple Inc.",
    "AAPU": "2x AAPL (Direxion)", "AGQ": "2x Silver (ProShares)",
    "AMZU": "2x AMZN (Direxion)", "BRKU": "2x BRK-B (Direxion)",
    "GALDY": "Galderma Group ADS", "GME": "GameStop Corp.",
    "GOOG": "Alphabet Inc. (C)", "HIMZ": "2x HIMS (Defiance)",
    "INTW": "2x INTC (GraniteShares)", "KO": "Coca-Cola Co.",
    "LCDL": "2x LCID (GraniteShares)", "LCID": "Lucid Group Inc.",
    "LULG": "2x LULU (LeverageShares)", "LULU": "Lululemon Athletica",
    "META": "Meta Platforms Inc.", "METU": "2x META (Direxion)",
    "MSFT": "Microsoft Corp.", "NFXL": "2x NFLX (Direxion)",
    "NKE": "Nike Inc.", "NVDA": "NVIDIA Corp.",
    "NVDL": "2x NVDA (GraniteShares)", "PMRTY": "Pop Mart Intl ADS",
    "PYPG": "2x PYPL (LeverageShares)", "QQQ": "Invesco QQQ Trust",
    "SCHD": "Schwab US Dividend ETF", "SOXS": "3x Short Semi (Direxion)",
    "SQQQ": "3x Short NDX (ProShares)", "SSO": "2x S&P500 (ProShares)",
    "TQQQ": "3x NDX (ProShares)", "TSLL": "2x TSLA (Direxion)",
    "UNH": "UnitedHealth Group", "UNHG": "2x UNH (LeverageShares)",
    "VOO": "Vanguard S&P500 ETF", "VT": "Vanguard Total World ETF",
    "VTI": "Vanguard Total Market ETF", "VUG": "Vanguard Growth ETF",
    "GOOGL": "Alphabet Inc. (A)", "TSM": "Taiwan Semi ADS",
}

# Pairs excluded from correlation: (stock, leveraged-ETF) and same-company
_SKIP_PAIRS = frozenset([
    ("AMD",   "AMDL"),  ("BABA",  "BABX"),  ("AAPL",  "AAPU"),
    ("BRK-B", "BRKU"),  ("GOOGL", "GGLL"),  ("GOOG",  "GGLL"),
    ("MSFT",  "MSFU"),  ("NVDA",  "NVDL"),  ("META",  "METU"),
    ("TSLA",  "TSLL"),  ("LCID",  "LCDL"),  ("LULU",  "LULG"),
    ("UNH",   "UNHG"),  ("QQQ",   "TQQQ"),  ("QQQ",   "SQQQ"),
    ("GOOG",  "GOOGL"),  # Same company: Alphabet A/C shares
])

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"


def skip_pair(t1: str, t2: str) -> bool:
    return (t1, t2) in _SKIP_PAIRS or (t2, t1) in _SKIP_PAIRS


# ---------------------------------------------------------------------------
# Technical indicators
# ---------------------------------------------------------------------------
def compute_rsi(arr: np.ndarray, period: int = 14) -> float:
    if len(arr) < period + 2:
        return float("nan")
    d = np.diff(arr.astype(float))
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    ag = float(np.mean(up[:period]))
    al = float(np.mean(dn[:period]))
    for i in range(period, len(d)):
        ag = (ag * (period - 1) + up[i]) / period
        al = (al * (period - 1) + dn[i]) / period
    return round(100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al), 2)


def classify(ret60d, ret120d, price, high52w) -> str:
    """TL if strong momentum AND not far below 52-week high."""
    if price is None or high52w is None or high52w <= 0:
        return "N"
    momentum = (ret60d is not None and ret60d >= 40.0) or \
               (ret120d is not None and ret120d >= 80.0)
    return "TL" if (momentum and price >= high52w * 0.80) else "N"


def compute_signal(cls, price, ma20, ma50, slope50, rsi14, peak60d, qqq5d):
    """Returns (signal, reason). SELL is checked before BUY."""
    if cls == "TL":
        if price < ma20 * 0.97:
            pct = (price / ma20 - 1) * 100
            return "SELL", f"TL: Broke below MA20 ({pct:.1f}% vs MA20)"
        if peak60d > 0 and price < peak60d * 0.82:
            dd = (price / peak60d - 1) * 100
            return "SELL", f"TL: {dd:.1f}% drawdown from 60d peak (threshold -18%)"
        if (price > ma50 and ma20 >= ma50 and slope50 > 0 and
                ma20 * 0.92 <= price <= ma20 * 1.02 and
                35 <= rsi14 <= 65 and qqq5d > -5):
            dist = (price / ma20 - 1) * 100
            return "BUY", (f"TL pullback setup: {dist:+.1f}% vs MA20, "
                           f"RSI {rsi14:.0f}, QQQ5d {qqq5d:+.1f}%")
        return "HOLD", (f"TL: No trigger — {(price/ma20-1)*100:+.1f}% vs MA20, "
                        f"RSI {rsi14:.0f}")
    else:
        if price < ma50:
            pct = (price / ma50 - 1) * 100
            return "SELL", f"N: Below MA50 ({pct:.1f}%)"
        if peak60d > 0 and price < peak60d * 0.90:
            dd = (price / peak60d - 1) * 100
            return "SELL", f"N: {dd:.1f}% drawdown from 60d peak (threshold -10%)"
        if (price > ma20 and price > ma50 and
                ma20 * 0.93 <= price <= ma20 * 1.00 and
                40 <= rsi14 <= 60 and qqq5d > 0):
            dist = (price / ma20 - 1) * 100
            return "BUY", (f"N dip setup: {dist:+.1f}% vs MA20, "
                           f"RSI {rsi14:.0f}, QQQ5d {qqq5d:+.1f}%")
        return "HOLD", (f"N: No trigger — {(price/ma20-1)*100:+.1f}% vs MA20, "
                        f"RSI {rsi14:.0f}")


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------
def run():
    print("=" * 60)
    print("Machine Learning Signal Platform — Analysis Pipeline")
    print(f"Tickers: {len(TICKERS)}")
    print("=" * 60)

    print("\nDownloading price data (2y)...")
    raw = yf.download(
        TICKERS, period="2y",
        auto_adjust=True, progress=False, threads=True,
    )

    if isinstance(raw.columns, pd.MultiIndex):
        close_all = raw["Close"]
    else:
        close_all = raw

    # QQQ 5-day return used as market filter
    qqq5d = 0.0
    if "QQQ" in close_all.columns:
        qs = close_all["QQQ"].dropna()
        if len(qs) >= 6:
            qqq5d = float((qs.iloc[-1] / qs.iloc[-6] - 1) * 100)
    print(f"QQQ 5d return: {qqq5d:+.2f}%")

    stocks, valid = [], []

    for ticker in TICKERS:
        try:
            if ticker not in close_all.columns:
                print(f"  SKIP  {ticker:8s} — no column")
                continue
            s = close_all[ticker].dropna()
            if len(s) < 55:
                print(f"  SKIP  {ticker:8s} — {len(s)} rows")
                continue

            arr = s.values.astype(float)
            px = float(arr[-1])
            ma20 = float(np.mean(arr[-20:])) if len(arr) >= 20 else px
            ma50 = float(np.mean(arr[-50:])) if len(arr) >= 50 else px

            # MA50 slope: today vs 10 trading days ago
            slope50 = (ma50 - float(np.mean(arr[-60:-10]))) if len(arr) >= 60 else 0.0

            rsi14 = compute_rsi(arr)
            if math.isnan(rsi14):
                rsi14 = 50.0

            def ret(d):
                return float((arr[-1] / arr[-(d + 1)] - 1) * 100) \
                    if len(arr) >= d + 1 else None

            r5, r20, r60, r120, r250 = ret(5), ret(20), ret(60), ret(120), ret(250)
            chg1d = float((arr[-1] / arr[-2] - 1) * 100) if len(arr) >= 2 else 0.0

            w52   = arr[-252:] if len(arr) >= 252 else arr
            high52 = float(np.max(w52))
            low52  = float(np.min(w52))
            peak60d = float(np.max(arr[-60:])) if len(arr) >= 60 else px

            cls = classify(r60, r120, px, high52)
            sig, reason = compute_signal(cls, px, ma20, ma50, slope50,
                                          rsi14, peak60d, qqq5d)

            stocks.append({
                "ticker":        ticker,
                "name":          TICKER_NAMES.get(ticker, ticker),
                "price":         round(px, 4),
                "change_1d":     round(chg1d, 2),
                "ma20":          round(ma20, 4),
                "ma50":          round(ma50, 4),
                "ma50_slope":    round(slope50, 4),
                "rsi14":         round(rsi14, 1),
                "ret5d":         round(r5,   2) if r5   is not None else None,
                "ret20d":        round(r20,  2) if r20  is not None else None,
                "ret60d":        round(r60,  2) if r60  is not None else None,
                "ret120d":       round(r120, 2) if r120 is not None else None,
                "ret250d":       round(r250, 2) if r250 is not None else None,
                "high52":        round(high52,  4),
                "low52":         round(low52,   4),
                "peak60d":       round(peak60d, 4),
                "dist_ma20_pct": round((px / ma20 - 1) * 100, 2),
                "dist_ma50_pct": round((px / ma50 - 1) * 100, 2),
                "classification": cls,
                "signal":        sig,
                "reason":        reason,
            })
            valid.append(ticker)

            r60s = f"{r60:+.1f}%" if r60 is not None else "n/a"
            print(f"  {sig:4s}  {cls:2s}  {ticker:8s}  "
                  f"${px:>10.4f}  RSI {rsi14:5.1f}  60d {r60s:>8}")

        except Exception as exc:
            print(f"  ERROR {ticker}: {exc}", file=sys.stderr)

    # Correlation (60-day daily returns, excluding skip-pairs)
    print(f"\nComputing correlation for {len(valid)} tickers...")
    avail = [t for t in valid if t in close_all.columns]
    ret_df = close_all[avail].pct_change().dropna().tail(62)

    corr_matrix, top_pos, top_neg = {}, [], []

    if len(ret_df) >= 20:
        C = ret_df.corr()
        for t in avail:
            corr_matrix[t] = {
                t2: (round(float(C.loc[t, t2]), 4)
                     if not math.isnan(C.loc[t, t2]) else 0.0)
                for t2 in avail
                if t in C.index and t2 in C.columns
            }

        pairs = []
        for i, t1 in enumerate(avail):
            for t2 in avail[i + 1:]:
                if skip_pair(t1, t2):
                    continue
                if t1 in C.index and t2 in C.columns:
                    v = C.loc[t1, t2]
                    if not math.isnan(v):
                        pairs.append([t1, t2, round(float(v), 4)])

        top_pos = sorted(pairs, key=lambda x: x[2], reverse=True)[:15]
        top_neg = sorted(pairs, key=lambda x: x[2])[:15]

    buy_c  = sum(1 for s in stocks if s["signal"] == "BUY")
    sell_c = sum(1 for s in stocks if s["signal"] == "SELL")
    hold_c = sum(1 for s in stocks if s["signal"] == "HOLD")
    tl_c   = sum(1 for s in stocks if s["classification"] == "TL")
    print(f"\nSummary: {len(stocks)} stocks | TL:{tl_c} | "
          f"BUY:{buy_c} | SELL:{sell_c} | HOLD:{hold_c}")

    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "qqq_5d_ret":   round(qqq5d, 2),
        "counts": {
            "total": len(stocks), "tl": tl_c,
            "buy": buy_c, "sell": sell_c, "hold": hold_c,
        },
        "stocks": stocks,
        "correlation": {
            "tickers":      avail,
            "matrix":       corr_matrix,
            "top_positive": top_pos,
            "top_negative": top_neg,
        },
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "analysis.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    run()
