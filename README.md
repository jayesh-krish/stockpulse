# StockPulse — real-data setup

## What's in this folder
- `index.html` — the dashboard (same UI you already had). It now loads `signals.json` instead of generating random numbers.
- `fetch_signals.py` — fetches real NSE EOD prices via Yahoo Finance and computes RSI/MACD/EMA/Bollinger Bands.
- `requirements.txt` — Python dependencies.
- `.github/workflows/update-signals.yml` — runs `fetch_signals.py` automatically on a schedule and commits the result.
- `signals.json` — generated output (not included yet — created the first time the script runs).

## One-time setup
1. Create a new **public** GitHub repo and push everything in this folder to it (public repos get free GitHub Pages + unlimited free Actions minutes).
2. Go to the repo's **Settings → Pages**. Under "Build and deployment", set Source to "Deploy from a branch", branch `main`, folder `/ (root)`. Save.
3. Go to the **Actions** tab, open "Update Stock Signals", click **Run workflow** to trigger it manually the first time (don't wait for the schedule). This creates `signals.json`.
4. Wait a minute, then visit `https://<your-username>.github.io/<repo-name>/` — your dashboard should now show real signals.

## After that
The workflow re-runs automatically every weekday at 4:30 PM IST (an hour after NSE close), recomputes signals, and commits the new `signals.json`. GitHub Pages picks up the change automatically — nothing else to do.

## To track different stocks
Edit the `STOCKS` list at the top of `fetch_signals.py` — add/remove entries with the NSE symbol, display name, and sector. If a stock's Yahoo Finance ticker differs from its NSE symbol, add a `"yf_ticker"` key.

## To run it locally instead (optional)
```bash
pip install -r requirements.txt
python fetch_signals.py
```
This writes `signals.json` in the current folder. Open `index.html` directly in a browser (or serve the folder with `python -m http.server`) to view it.
