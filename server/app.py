import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fetch_prices import fetch_prices

app = FastAPI(title="Portfolio Dashboard API")

# --- Configuration ---
# Optional:
#   DASH_CORS_ORIGINS  : comma-separated list of allowed origins (default '*')

cors = os.getenv("DASH_CORS_ORIGINS", "*")
allow_origins = [o.strip() for o in cors.split(",") if o.strip()] if cors != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["GET","POST"],
    allow_headers=["*"],
)


@app.get("/api/data")
async def data():
    prices = fetch_prices()

    # Placeholder signals/performance — replace with your logic later
    rows = {}
    for k, v in prices.get("rows", {}).items():
        rows[k] = {
            "price": v,
            "signal": {"algo": "TBD", "ml": "TBD", "oo": "TBD"},
            "performance": {"algo": "TBD", "ml": "TBD", "oo": "TBD"},
        }

    return {
        "last_updated": prices.get("last_updated"),
        "rows": rows,
    }
