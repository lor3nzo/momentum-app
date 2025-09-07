import os
import csv
import asyncio
import datetime as dt
import numpy as np
import pandas as pd

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import httpx

# ----- Alpaca Market Data config -----
APCA_KEY = os.getenv("APCA_API_KEY_ID")
APCA_SECRET = os.getenv("APCA_API_SECRET_KEY")
FEED = os.getenv("ALPACA_FEED", "iex")  # or "sip" on paid plans
DATA_BASE = "https://data.alpaca.markets/v2"

app = FastAPI()

# Serve frontend (CSS/JS) and index.html
app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse("frontend/index.html")


# ---------- data fetch ----------
async def fetch_bars(sym: str, start_iso: str, end_iso: str) -> pd.DataFrame | None:
    """Fetch daily bars for a symbol from Alpaca. Returns DataFrame or None if empty."""
    if not APCA_KEY or not APCA_SECRET:
        raise HTTPException(status_code=500, detail="Missing Alpaca credentials. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY.")

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
        "feed": FEED,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{DATA_BASE}/stocks/{sym}/bars", headers=headers, params=params)
        if r.status_code != 200:
            # bubble up Alpaca error message
            raise HTTPException(status_code=r.status_code, detail=r.text)

    js = r.json()
    bars = js.get("bars", [])
    if not bars:
        return None

    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df = df.sort_values("t").reset_index(drop=True)
    df = df.rename(columns={"t": "date", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    return df[["date", "open", "high", "low", "close", "volume"]]


# ---------- analytics ----------
async def compute_scores(days_back: int = 600):
    """Load tickers.csv, fetch data, compute momentum & summary rows."""
    # Load tickers
    tickers: list[str] = []
    csv_path = os.path.join(os.getcwd(), "tickers.csv")
    if os.path.exists(csv_path):
        with open(csv_path, newline="") as f:
            r = csv.reader(f)
            for row in r:
                if not row:
                    continue
                sym = row[0].strip().upper()
                if sym and sym != "SYMBOL":
                    tickers.append(sym)
    if not tickers:
        tickers = ["AAPL"]

    # Date window
    end = dt.datetime.utcnow().date()
    start = end - dt.timedelta(days=int(max(380, min(days_back, 1200))))
    start_iso = f"{start.isoformat()}T00:00:00Z"
    end_iso = f"{end.isoformat()}T23:59:59Z"

    async def fetch_one(sym: str):
        try:
            df = await fetch_bars(sym, start_iso, end_iso)
            return sym, df
        except Exception:
            return sym, None

    results = await asyncio.gather(*[fetch_one(s) for s in tickers])

    rows: list[dict] = []
    for sym, df in results:
        if df is None or len(df) < 220:
            continue

        s = df["close"].astype(float).to_numpy()

        # SMAs
        sma50 = pd.Series(s).rolling(50).mean()
        sma200 = pd.Series(s).rolling(200).mean()
        trend_50_gt_200 = int(
            (not np.isnan(sma50.iloc[-1])) and (not np.isnan(sma200.iloc[-1])) and (sma50.iloc[-1] > sma200.iloc[-1])
        )
        ts_mom_sign = 1 if s[-1] >= (sma200.iloc[-1] if not np.isnan(sma200.iloc[-1]) else s[-1]) else -1

        # Simple momentum legs (total returns)
        def total_return(n):
            if len(s) <= n:
                return np.nan
            return (s[-1] / s[-n - 1]) - 1.0

        S1 = total_return(252)   # ~12m
        S2 = total_return(126)   # ~6m
        S3 = total_return(63)    # ~3m

        # Z-score of last 60d return vs 1y window of daily returns
        look = 60
        if len(s) > look + 1:
            r = pd.Series(s).pct_change().dropna()
            last = (s[-1] / s[-look - 1]) - 1.0
            mu = r.rolling(252).mean().iloc[-1]
            sd = r.rolling(252).std().iloc[-1]
            z = (last - (mu if pd.notna(mu) else 0.0)) / (sd + 1e-9)
        else:
            z = np.nan

        ann_vol = float(pd.Series(s).pct_change().std() * np.sqrt(252))

        rows.append(
            {
                "symbol": sym,
                "S1": float(S1) if pd.notna(S1) else None,
                "S2": float(S2) if pd.notna(S2) else None,
                "S3": float(S3) if pd.notna(S3) else None,
                "Z_mom": float(z) if pd.notna(z) else None,
                "trend50>200": trend_50_gt_200,
                "ts_mom_sign": 1 if ts_mom_sign >= 0 else -1,
                "ann_vol": ann_vol,
                "penalty": 0.0,  # hook for future filters (earnings, etc.)
            }
        )

    if not rows:
        return [], tickers

    # Rank S1,S2,S3 (0..100) with weights 60/30/10
    df_all = pd.DataFrame(rows)

    def rank01(col: str) -> pd.Series:
        s = df_all[col]
        mask = s.notna()
        if mask.sum() <= 1:
            return pd.Series([np.nan] * len(s))
        ranks = s[mask].rank(pct=True)  # 0..1
        out = pd.Series([np.nan] * len(s), index=s.index)
        out[mask] = ranks
        return out

    r1 = rank01("S1")
    r2 = rank01("S2")
    r3 = rank01("S3")
    score = (0.6 * r1.fillna(0) + 0.3 * r2.fillna(0) + 0.1 * r3.fillna(0)) * 100.0
    df_all["MomentumScore"] = score.round(3)

    # Simple entry rule (example): trend filter AND positive 6m
    df_all["enter_long"] = ((df_all["trend50>200"] == 1) & (df_all["S2"].fillna(0) > 0)).astype(bool)

    # Breadth = share with Z_mom > 0
    valid = df_all["Z_mom"].notna()
    breadth = float((df_all.loc[valid, "Z_mom"] > 0).mean()) if valid.any() else None

    out_rows = df_all.sort_values("MomentumScore", ascending=False).to_dict(orient="records")
    return out_rows, tickers, breadth


# ---------- API endpoints ----------
@app.get("/api/scores")
async def api_scores(days_back: int = 600) -> JSONResponse:
    rows, symbols, breadth = await compute_scores(days_back=days_back)
    return JSONResponse(
        {
            "as_of": dt.datetime.utcnow().strftime("%Y-%m-%d"),
            "breadth": breadth,
            "symbols": symbols,
            "rows": rows,
        }
    )


@app.get("/api/spark")
async def api_spark(symbol: str = Query(..., min_length=1), days: int = 120) -> JSONResponse:
    """Tiny sparkline data (recent closes) for a symbol."""
    end = dt.datetime.utcnow().date()
    start = end - dt.timedelta(days=int(max(30, min(days, 365))))
    start_iso = f"{start.isoformat()}T00:00:00Z"
    end_iso = f"{end.isoformat()}T23:59:59Z"

    df = await fetch_bars(symbol.upper(), start_iso, end_iso)
    if df is None or df.empty:
        return JSONResponse({"symbol": symbol.upper(), "dates": [], "closes": []})

    closes = df["close"].astype(float).tolist()[-60:]
    dates = [d.strftime("%Y-%m-%d") for d in df["date"].tolist()[-60:]]
    return JSONResponse({"symbol": symbol.upper(), "dates": dates, "closes": closes})
