import os
import datetime as dt
from typing import List, Dict

import httpx
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .momentum import compute_scores

load_dotenv()

APCA_KEY = os.getenv("APCA_API_KEY_ID", "")
APCA_SECRET = os.getenv("APCA_API_SECRET_KEY", "")
ALPACA_FEED = os.getenv("ALPACA_FEED", "iex")

if not APCA_KEY or not APCA_SECRET:
    print("[WARN] Alpaca credentials are not set. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY.")

DATA_BASE = "https://data.alpaca.markets/v2"

app = FastAPI(title="Momentum Meter (Alpaca)", version="1.0")

# Serve static frontend
app.mount("/static", StaticFiles(directory="frontend", html=True), name="static")

@app.get("/", response_class=HTMLResponse)
def root():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

def read_tickers_csv(path: str = "tickers.csv") -> List[str]:
    if not os.path.exists(path):
        return ["AAPL", "MSFT"]
    df = pd.read_csv(path)
    syms = [str(s).strip().upper() for s in df["symbol"].to_list() if str(s).strip()]
    return syms

async def fetch_bars(symbol: str, start_iso: str, end_iso: str) -> pd.DataFrame:
    url = f"{DATA_BASE}/stocks/{symbol}/bars"
    headers = {
        "APCA-API-KEY-ID": APCA_KEY,
        "APCA-API-SECRET-KEY": APCA_SECRET,
        "accept": "application/json",
    }
    params = {
        "timeframe": "1Day",
        "start": start_iso,
        "end": end_iso,
        "limit": 5000,
        "adjustment": "raw",
        "feed": ALPACA_FEED,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params=params)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"{symbol}: HTTP {r.status_code} {r.text}")
        js = r.json()
    bars = js.get("bars", [])
    if not bars:
        raise HTTPException(status_code=404, detail=f"{symbol}: no bars returned")
    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df = df.sort_values("t").reset_index(drop=True)
    df.rename(columns={"t":"date","o":"open","h":"high","l":"low","c":"close","v":"volume"}, inplace=True)
    return df[["date","open","high","low","close","volume"]]

@app.get("/api/scores")
async def api_scores(days_back: int = 600) -> JSONResponse:
    """Returns momentum metrics and MomentumScore for all tickers in tickers.csv.
    Query param: days_back (calendar days)."""
    end = dt.datetime.utcnow().date()
    start = end - dt.timedelta(days=int(days_back))
    start_iso = start.isoformat() + "T00:00:00Z"
    end_iso = end.isoformat() + "T23:59:59Z"

    symbols = read_tickers_csv()
    universe: Dict[str, pd.DataFrame] = {}
    errors: Dict[str, str] = {}

    for sym in symbols:
        try:
            df = await fetch_bars(sym, start_iso, end_iso)
            universe[sym] = df
        except HTTPException as e:
            errors[sym] = str(e.detail)
            universe[sym] = None

    table, breadth = compute_scores(universe)
    table = table.sort_values("MomentumScore", ascending=False)

    return JSONResponse({
        "breadth": float(breadth) if not (np.isnan(breadth)) else None,
        "as_of": end.isoformat(),
        "symbols": symbols,
        "errors": errors,
        "rows": table.to_dict(orient="records")
    })
