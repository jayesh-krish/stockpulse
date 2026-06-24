"""
fetch_signals.py

Fetches real NSE end-of-day price/volume data (via yfinance), computes the
same RSI / MACD / EMA / Bollinger Band indicators the StockPulse dashboard
displays, and writes the result to signals.json.

The dashboard (index.html) never calculates anything itself anymore -- it
just loads signals.json and renders it. This script is what GitHub Actions
runs on a schedule to keep that file fresh.

Run locally:
    pip install -r requirements.txt
    python fetch_signals.py
"""

import json
import time
from datetime import datetime, timezone

import yfinance as yf

# ---- Stock universe — edit this list to track whatever stocks you want ----
# "yf_ticker" is only needed when the Yahoo Finance ticker differs from the
# NSE display symbol (e.g. HDFC Bank's NSE symbol is HDFCBANK, not HDFC).
STOCKS = [
  {"symbol": "ADANIENT", "name": "Adani Enterprises", "sector": "Metals & Mining"},
  {"symbol": "ADANIPORTS", "name": "Adani Ports and SEZ", "sector": "Infrastructure"},
  {"symbol": "APOLLOHOSP", "name": "Apollo Hospitals Enterprise", "sector": "Healthcare"},
  {"symbol": "ASIANPAINT", "name": "Asian Paints", "sector": "Consumer Durables"},
  {"symbol": "AXISBANK", "name": "Axis Bank", "sector": "Banking"},
  {"symbol": "BAJAJ-AUTO", "name": "Bajaj Auto", "sector": "Automobile"},
  {"symbol": "BAJFINANCE", "name": "Bajaj Finance", "sector": "Financial Services"},
  {"symbol": "BAJAJFINSV", "name": "Bajaj Finserv", "sector": "Financial Services"},
  {"symbol": "BEL", "name": "Bharat Electronics", "sector": "Capital Goods"},
  {"symbol": "BHARTIARTL", "name": "Bharti Airtel", "sector": "Telecommunication"},
  {"symbol": "CIPLA", "name": "Cipla", "sector": "Healthcare"},
  {"symbol": "COALINDIA", "name": "Coal India", "sector": "Metals & Mining"},
  {"symbol": "DRREDDY", "name": "Dr. Reddy's Laboratories", "sector": "Healthcare"},
  {"symbol": "EICHERMOT", "name": "Eicher Motors", "sector": "Automobile"},
  {"symbol": "ETERNAL", "name": "Eternal", "sector": "Unclassified"},
  {"symbol": "GRASIM", "name": "Grasim Industries", "sector": "Construction Materials"},
  {"symbol": "HCLTECH", "name": "HCL Technologies", "sector": "IT"},
  {"symbol": "HDFCBANK", "name": "HDFC Bank", "sector": "Banking"},
  {"symbol": "HDFCLIFE", "name": "HDFC Life Insurance", "sector": "Financial Services"},
  {"symbol": "HEROMOTOCO", "name": "Hero MotoCorp", "sector": "Automobile"},
  {"symbol": "HINDALCO", "name": "Hindalco Industries", "sector": "Metals & Mining"},
  {"symbol": "HINDUNILVR", "name": "Hindustan Unilever", "sector": "FMCG"},
  {"symbol": "ICICIBANK", "name": "ICICI Bank", "sector": "Banking"},
  {"symbol": "INDUSINDBK", "name": "IndusInd Bank", "sector": "Banking"},
  {"symbol": "INFY", "name": "Infosys", "sector": "IT"},
  {"symbol": "ITC", "name": "ITC", "sector": "FMCG"},
  {"symbol": "JIOFIN", "name": "Jio Financial Services", "sector": "Financial Services"},
  {"symbol": "JSWSTEEL", "name": "JSW Steel", "sector": "Metals & Mining"},
  {"symbol": "KOTAKBANK", "name": "Kotak Mahindra Bank", "sector": "Banking"},
  {"symbol": "LT", "name": "Larsen & Toubro", "sector": "Construction"},
  {"symbol": "M&M", "name": "Mahindra & Mahindra", "sector": "Automobile"},
  {"symbol": "MARUTI", "name": "Maruti Suzuki India", "sector": "Automobile"},
  {"symbol": "NESTLEIND", "name": "Nestlé India", "sector": "FMCG"},
  {"symbol": "NTPC", "name": "NTPC", "sector": "Power"},
  {"symbol": "ONGC", "name": "ONGC", "sector": "Energy"},
  {"symbol": "POWERGRID", "name": "Power Grid Corporation", "sector": "Power"},
  {"symbol": "RELIANCE", "name": "Reliance Industries", "sector": "Energy"},
  {"symbol": "SBILIFE", "name": "SBI Life Insurance", "sector": "Financial Services"},
  {"symbol": "SBIN", "name": "State Bank of India", "sector": "Banking"},
  {"symbol": "SHRIRAMFIN", "name": "Shriram Finance", "sector": "Financial Services"},
  {"symbol": "SUNPHARMA", "name": "Sun Pharmaceutical Industries", "sector": "Healthcare"},
  {"symbol": "TATACONSUM", "name": "Tata Consumer Products", "sector": "FMCG"},
  {"symbol": "TATAMOTORS", "name": "Tata Motors", "sector": "Automobile"},
  {"symbol": "TATASTEEL", "name": "Tata Steel", "sector": "Metals & Mining"},
  {"symbol": "TCS", "name": "Tata Consultancy Services", "sector": "IT"},
  {"symbol": "TECHM", "name": "Tech Mahindra", "sector": "IT"},
  {"symbol": "TITAN", "name": "Titan Company", "sector": "Consumer Durables"},
  {"symbol": "TRENT", "name": "Trent", "sector": "Retail"},
  {"symbol": "ULTRACEMCO", "name": "UltraTech Cement", "sector": "Construction Materials"},
  {"symbol": "WIPRO", "name": "Wipro", "sector": "IT"}
]

HISTORY_PERIOD = "4mo"  # enough bars for EMA21 / MACD(12,26,9) / BB(20) to settle
KEEP_DAYS = 31          # trim to the last N days for the dashboard's charts


# ---------------------------------------------------------------------------
# Indicator math — deliberately mirrors the JS that used to run in the
# browser (same RSI/MACD/EMA/BB formulas), so signals are computed the same
# way whether you're looking at the dashboard or debugging this script.
# ---------------------------------------------------------------------------

def calc_ema(prices, period):
    k = 2 / (period + 1)
    ema = [prices[0]]
    for i in range(1, len(prices)):
        ema.append(prices[i] * k + ema[i - 1] * (1 - k))
    return ema


def calc_rsi(prices, period=14):
    rsi = [None] * period
    for i in range(period, len(prices)):
        gains = losses = 0.0
        for j in range(i - period, i):
            diff = prices[j + 1] - prices[j]
            if diff > 0:
                gains += diff
            else:
                losses += -diff
        avg_g, avg_l = gains / period, losses / period
        if avg_l == 0:
            rsi.append(100)
            continue
        rs = avg_g / avg_l
        rsi.append(round(100 - (100 / (1 + rs))))
    return rsi


def calc_macd(prices):
    ema12 = calc_ema(prices, 12)
    ema26 = calc_ema(prices, 26)
    macd = [round(a - b, 2) for a, b in zip(ema12, ema26)]
    signal_raw = calc_ema(macd[26:], 9) if len(macd) > 26 else []
    signal_full = [None] * 26 + signal_raw
    hist = [
        round(macd[i] - signal_full[i], 2) if signal_full[i] is not None else None
        for i in range(len(macd))
    ]
    return {"macd": macd, "signal": signal_full, "hist": hist}


def calc_bb(prices, period=20, mult=2):
    upper, lower, middle = [], [], []
    for i in range(len(prices)):
        if i < period - 1:
            upper.append(None)
            lower.append(None)
            middle.append(None)
            continue
        window = prices[i - period + 1 : i + 1]
        avg = sum(window) / period
        std = (sum((v - avg) ** 2 for v in window) / period) ** 0.5
        upper.append(round(avg + mult * std, 2))
        lower.append(round(avg - mult * std, 2))
        middle.append(round(avg, 2))
    return {"upper": upper, "lower": lower, "middle": middle}


def build_signal(prices, rsi_arr, macd_data, bb_data, ema9, ema21):
    last = len(prices) - 1
    rsi = rsi_arr[last]
    score = 0
    signals = []

    if rsi is not None:
        if rsi < 30:
            score += 1
            signals.append("RSI Oversold")
        elif rsi > 70:
            score -= 1
            signals.append("RSI Overbought")

    macd, sig = macd_data["macd"][last], macd_data["signal"][last]
    macd_prev, sig_prev = macd_data["macd"][last - 1], macd_data["signal"][last - 1]
    if sig is not None and sig_prev is not None:
        if macd > sig and macd_prev <= sig_prev:
            score += 2
            signals.append("MACD Crossover ↑")
        elif macd < sig and macd_prev >= sig_prev:
            score -= 2
            signals.append("MACD Crossover ↓")
        elif macd > sig:
            score += 1
            signals.append("MACD Bullish")
        elif macd < sig:
            score -= 1
            signals.append("MACD Bearish")

    bb_u, bb_l = bb_data["upper"][last], bb_data["lower"][last]
    p = prices[last]
    if bb_l is not None and p < bb_l:
        score += 1
        signals.append("Near BB Lower")
    elif bb_u is not None and p > bb_u:
        score -= 1
        signals.append("Near BB Upper")

    if ema9[last] > ema21[last] and ema9[last - 1] <= ema21[last - 1]:
        score += 1
        signals.append("Golden Cross")
    elif ema9[last] < ema21[last] and ema9[last - 1] >= ema21[last - 1]:
        score -= 1
        signals.append("Death Cross")

    if score >= 3:
        label, cls = "STRONG BUY", "signal-strong-buy"
    elif score >= 1:
        label, cls = "BUY", "signal-buy"
    elif score <= -3:
        label, cls = "STRONG SELL", "signal-sell"
    elif score <= -1:
        label, cls = "SELL", "signal-sell"
    else:
        label, cls = "HOLD", "signal-hold"

    strength = min(abs(score) / 4, 1)
    return {"label": label, "cls": cls, "score": score, "strength": strength, "signals": signals}


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_stock(symbol, yf_ticker=None):
    ticker = f"{yf_ticker or symbol}.NS"
    try:
        df = yf.download(
            ticker, period=HISTORY_PERIOD, interval="1d",
            progress=False, auto_adjust=True,
        )
    except Exception as e:
        print(f"  ! {symbol}: download failed ({e})")
        return None

    if df is None or df.empty:
        print(f"  ! {symbol}: no data returned (delisted, renamed, or bad ticker?)")
        return None

    # newer yfinance versions can return MultiIndex columns even for one ticker
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    df = df.dropna(subset=["Close"])
    if len(df) < 35:
        print(f"  ! {symbol}: only {len(df)} rows, need 35+ for MACD to settle")
        return None

    closes = [round(float(v), 2) for v in df["Close"].tolist()]
    volumes = [int(v) for v in df["Volume"].tolist()]

    rsi_arr = calc_rsi(closes)
    macd_data = calc_macd(closes)
    bb_data = calc_bb(closes)
    ema9 = calc_ema(closes, 9)
    ema21 = calc_ema(closes, 21)
    signal = build_signal(closes, rsi_arr, macd_data, bb_data, ema9, ema21)

    last = len(closes) - 1
    change = round((closes[last] - closes[last - 1]) / closes[last - 1] * 100, 2)
    recent_vols = volumes[-21:-1] or volumes[-1:]
    avg_vol = round(sum(recent_vols) / len(recent_vols))

    def trim(arr):
        return arr[-KEEP_DAYS:]

    return {
        "symbol": symbol,
        "price": closes[last],
        "change": change,
        "rsi": rsi_arr[last],
        "macdVal": macd_data["macd"][last],
        "volume": volumes[last],
        "avgVol": avg_vol,
        "prices": trim(closes),
        "rsiArr": trim(rsi_arr),
        "macdData": {k: trim(v) for k, v in macd_data.items()},
        "bbData": {k: trim(v) for k, v in bb_data.items()},
        "ema9": trim(ema9),
        "ema21": trim(ema21),
        "signal": signal,
    }


def main():
    print(f"Fetching {len(STOCKS)} stocks from Yahoo Finance...")
    stocks_out = {}
    for s in STOCKS:
        symbol = s["symbol"]
        print(f"  -> {symbol}")
        data = fetch_stock(symbol, s.get("yf_ticker"))
        if data is None:
            continue
        data["name"] = s["name"]
        data["sector"] = s["sector"]
        stocks_out[symbol] = data
        time.sleep(1)  # be polite to Yahoo's servers

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stocks": stocks_out,
    }

    with open("signals.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote signals.json with {len(stocks_out)}/{len(STOCKS)} stocks.")
    if len(stocks_out) == 0:
        raise SystemExit("No stocks fetched successfully — failing the run.")


if __name__ == "__main__":
    main()
