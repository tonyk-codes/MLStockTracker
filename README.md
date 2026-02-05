# Portfolio Dashboard

A finance-style, white-theme stock dashboard designed for a GitHub repo homepage.

## What you asked for (and what this repo provides)

- ✅ **Single-page dashboard** (index.html) with three tables.
- ✅ **Professional finance look** (white background, navy accents).
- ✅ **Sticky header** with passcode input + filters (Cat. / Grade) + **Last updated**.
- ✅ **Full stock names** in the Stock column.
- ✅ **True passcode gating (real security)** **requires a backend**.

### Important: GitHub Pages is static
GitHub Pages cannot run Python or any server-side authentication.
That means **true security is not possible with only index.html**.

To get real security, you must host a backend that:
1) verifies the passcode **server-side**, and
2) only returns protected data (prices/signals/performance) after authentication.

This ZIP includes a minimal backend under `/server`.

---

## Option A (Recommended for true security): Run the included secure backend

### 1) Install and run locally

```bash
cd server
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt

# Set secrets (choose strong values)
export DASH_PASSCODE='YOUR_STRONG_PASSCODE'
export DASH_SECRET_KEY='A_LONG_RANDOM_STRING'

uvicorn app:app --reload --port 8000
```

Open http://localhost:8000

### 2) Deploy to the internet
Deploy the `/server` folder to a host that supports Python (Render, Fly.io, Azure App Service, etc.).
Then serve the frontend from the same origin OR configure CORS.

> If you want to keep GitHub Pages for frontend, you’ll need the backend on another domain + CORS.

---

## Live prices via Yahoo Finance (yfinance)
The backend uses **yfinance** to fetch:
- regular market price
- pre-market price (when available)
- post-market price (when available)

The UI shows:
- `Price` (regular)
- subline: `Pre … | Post …`

---

## File structure

- `index.html` – the dashboard page
- `styles.css` – styling (finance white theme)
- `app.js` – table render, filters, secure login flow
- `server/app.py` – FastAPI backend (secure passcode + protected data)
- `server/fetch_prices.py` – yfinance data fetch helper
- `server/requirements.txt` – backend deps

---

## Notes
- The *algorithm/ML/OB-OS* fields are placeholders (TBD) until you implement your logic.
- The backend is where you can later compute signals/performance and return them in `/api/data`.

