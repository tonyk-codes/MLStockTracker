# ML Stock Tracker (Streamlit)

This repository is Streamlit + Heroku only.

## Features

- Dark theme UI (non-blue primary background).
- Top-banner `Refresh` button.
- Two main action buttons:
	- `Obtain Stock Price & yfinance Info`
	- `Start Analysis / ML`
- Live data only (no synthetic fallback rows).
- Price display fields:
	- current price
	- percentage change
	- lowest today
	- highest today
- Clickable stock name and ticker links to Yahoo Finance.
- Add more stocks using a ticker input field.
- News sentiment section with trend/volume charts for selected stock.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

If `streamlit` is not recognized, run with Python directly:

```bash
python -m streamlit run app.py
```

If you accidentally typed `strealit`, use `streamlit`.

Then open the URL shown by Streamlit (usually `http://localhost:8501`).

## Deploy on Heroku

This project is ready for Heroku using `Procfile`.

### 1) Create Heroku app

```bash
heroku login
heroku create your-ml-stock-tracker
```

### 2) Deploy

```bash
git add .
git commit -m "Prepare Streamlit app for Heroku"
git push heroku main
```

If your branch is `master`, use:

```bash
git push heroku master
```

### 3) Open app

```bash
heroku open
```

### Notes

- Heroku uses the command in `Procfile`:
	- `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`
- `runtime.txt` pins the Python version for repeatable deploys.
- yfinance calls require outbound internet access from the dyno.

## Project files

- `app.py` - main Streamlit application
- `requirements.txt` - Python dependencies
- `Procfile` - Heroku web process command
- `runtime.txt` - Python runtime pin for Heroku

