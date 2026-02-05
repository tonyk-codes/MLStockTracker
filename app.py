import os
import time
import hmac
import json
import base64
import hashlib

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fetch_prices import fetch_prices

app = FastAPI(title="Portfolio Dashboard API")

# --- Configuration ---
# Required env vars:
#   DASH_PASSCODE   : passcode (keep secret on server)
#   DASH_SECRET_KEY : long random string used to sign tokens
# Optional:
#   DASH_TOKEN_TTL_SEC : token lifetime (default 3600)
#   DASH_CORS_ORIGINS  : comma-separated list of allowed origins (default '*')

PASSCODE = os.getenv("DASH_PASSCODE", "")
SECRET_KEY = os.getenv("DASH_SECRET_KEY", "")
TOKEN_TTL = int(os.getenv("DASH_TOKEN_TTL_SEC", "3600"))

cors = os.getenv("DASH_CORS_ORIGINS", "*")
allow_origins = [o.strip() for o in cors.split(",") if o.strip()] if cors != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["GET","POST"],
    allow_headers=["*"],
)

# --- Helpers ---

def _require_env():
    if not PASSCODE or not SECRET_KEY:
        raise HTTPException(status_code=500, detail="Server not configured: missing DASH_PASSCODE or DASH_SECRET_KEY")


def _pbkdf2(passcode: str, salt: bytes, rounds: int = 200_000) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", passcode.encode("utf-8"), salt, rounds)


def _verify_passcode(passcode: str) -> bool:
    # Derive + constant-time compare against derived server passcode.
    # Passcode itself is never stored in the repo.
    salt = b"portfolio-dashboard-salt-v1"
    a = _pbkdf2(passcode, salt)
    b = _pbkdf2(PASSCODE, salt)
    return hmac.compare_digest(a, b)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "==")


def _sign(payload: dict) -> str:
    msg = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
    return _b64url(msg) + "." + _b64url(sig)


def _verify_token(token: str) -> None:
    try:
        msg_b64, sig_b64 = token.split(".")
        msg = _b64url_decode(msg_b64)
        sig = _b64url_decode(sig_b64)
        expected = hmac.new(SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        payload = json.loads(msg.decode("utf-8"))
        exp = float(payload.get("exp", 0))
        if time.time() > exp:
            raise ValueError("expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.post("/api/login")
async def login(req: Request):
    _require_env()
    body = await req.json()
    passcode = body.get("passcode", "")
    if not isinstance(passcode, str) or len(passcode) < 1:
        raise HTTPException(status_code=400, detail="Missing passcode")

    if not _verify_passcode(passcode):
        raise HTTPException(status_code=401, detail="Access denied")

    exp = time.time() + TOKEN_TTL
    token = _sign({"exp": exp, "v": 1})
    return {"token": token, "expires_in": TOKEN_TTL}


@app.post("/api/logout")
async def logout():
    # Stateless token: client deletes it; endpoint exists for symmetry.
    return {"ok": True}


@app.get("/api/data")
async def data(req: Request):
    _require_env()

    auth = req.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = auth.split(" ", 1)[1].strip()
    _verify_token(token)

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
