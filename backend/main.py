import os, datetime as dt
import pandas as pd, numpy as np
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
import httpx

APCA_KEY = os.getenv("APCA_API_KEY_ID")
APCA_SECRET = os.getenv("APCA_API_SECRET_KEY")
FEED = os.getenv("ALPACA_FEED", "iex")
DATA_BASE = "https://data.alpaca.markets/v2"

app = FastAPI()

async def fetch_bars(sym, start_iso, end_iso):
    headers = {"APCA-API-KEY-ID": APCA_KEY, "APCA-API-SECRET-KEY": APCA_SECRET, "accept": "application/json"}
    params = {"timeframe":"1Day","start":start_iso,"end":end_iso,"limit":5000,"adjustment":"raw","feed":FEED}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DATA_BASE}/stocks/{sym}/bars", headers=headers, params=params)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)
        js = r.json()
        bars = js.get("bars", [])
        if not bars: return None
        df = pd.DataFrame(bars)
        df["t"] = pd.to_datetime(df["t"])
        df = df.sort_values("t").reset_index(drop=True)
        return df.rename(columns={"t":"date","o":"open","h":"high","l":"low","c":"close","v":"volume"})[["date","open","high","low","close","volume"]]

@app.get("/api/scores")
async def api_scores(days_back: int = 600) -> JSONResponse:
    return JSONResponse({"as_of":"demo","breadth":0.5,"symbols":["AAPL"],"rows":[{"symbol":"AAPL","MomentumScore":80,"Z_mom":1.2,"S1":70,"S2":100,"S3":60,"penalty":0,"ann_vol":0.25,"trend50>200":1,"ts_mom_sign":1,"enter_long":True}]} )

@app.get("/api/spark")
async def api_spark(symbol: str = Query(..., min_length=1), days: int = 90) -> JSONResponse:
    end = dt.datetime.utcnow().date()
    start = end - dt.timedelta(days=int(max(30, min(days, 365))))
    start_iso = start.isoformat() + "T00:00:00Z"
    end_iso = end.isoformat() + "T23:59:59Z"
    try:
        df = await fetch_bars(symbol.upper(), start_iso, end_iso)
    except HTTPException as e:
        raise e
    if df is None:
        return JSONResponse({"symbol":symbol.upper(),"dates":[],"closes":[]})
    closes = df["close"].astype(float).tolist()[-60:]
    dates = [d.strftime("%Y-%m-%d") for d in df["date"].tolist()[-60:]]
    return JSONResponse({"symbol":symbol.upper(),"dates":dates,"closes":closes})
