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

# ----- Alpaca config -----
APCA_KEY = os.getenv("APCA_API_KEY_ID")
APCA_SECRET = os.getenv("APCA_API_SECRET_KEY")
FEED = os.getenv("ALPACA_FEED", "iex")  # or "sip" on paid plans

DATA_BASE = "https://data.alpaca.markets/v2"  # market data (bars)
ASSETS_BASE = "https://api.alpaca.markets/v2"  # trading API for asset metadata (names)

# simple in-memory cache for company names
NAMES_CACHE: dict[str, str | None] = {}

# simple concurrency limiter for outbound calls
SEM = asyncio.Semaphore(8)

app = FastAPI()

# ---- Serve frontend (CSS/JS) and index.html ----
FRONTEND_DIR = os.path.join(os.getcwd(), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", include_in_schema=False)
def root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return JSONResponse(
        {"message": "UI not found. Place frontend/index.html and /static assets."},
        status_code=404,
    )


# ---------- helpers: CSV loading & name lookup ----------
def load_tickers_with_names() -> list[tuple[str, str | None]]:
    """
    Read tickers.csv. Supports:
      - 1 column: symbol
      - 2 columns: symbol,name
    Returns: list of (symbol, name_or_none)
    """
    path = os.path.join(os.getcwd(), "tickers.csv")
    out: list[tuple[str, str | None]] = []
    if not os.path.exists(path):
        return [("AAPL", None)]

    with open(path, newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # Strip header if present
    if rows and rows[0] and rows[0][0].strip().lower() == "symbol":
        rows = rows[1:]

    for row in rows:
        if not row:
            continue
        sym = (row[0] or "").strip().upper()
        if not sym:
            continue
        name = (row[1].strip() if len(row) > 1 else None) or None
        out.append((sym, name))
    return out or [("AAPL", None)]


async def fetch_company_name(symbol: str) -> str | None:
    """
    Fetch company name from Alpaca Assets API.
    Uses NAMES_CACHE to avoid repeated calls.
    """
    sym = symbol.upper()
    if sym in NAMES_CACHE:
        return NAMES_CACHE[sym]

    headers = {
        "APCA-API-KEY-ID": APCA_KEY or "",
        "APCA-API-SECRET-KEY": APCA_SECRET or "",
        "accept": "application/json",
    }
    url = f"{ASSETS_BASE}/assets/{sym}"
    try:
        async with SEM:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(url, headers=headers)
        if r.status_code != 200:
            NAMES_CACHE[sym] = None
            return None
        name = r.json().get("name")
    except Exception:
        name = None

    NAMES_CACHE[sym] = name
    return name


# ---------- market data fetch ----------
async def fetch_bars(sym: str, start_iso: str, end_iso: str) -> pd.DataFrame | None:
    """Fetch daily bars for a symbol from Alpaca. Returns DataFrame or None if empty."""
    if not APCA_KEY or not APCA_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Missing Alpaca credentials. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY.",
        )

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

    async with SEM:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{DATA_BASE}/stocks/{sym}/bars", headers=headers, params=params)
            if r.status_code != 200:
                msg = r.text
                if isinstance(msg, str) and len(msg) > 500:
                    msg = msg[:500] + "...(truncated)"
                raise HTTPException(status_code=r.status_code, detail=msg)

    js = r.json()
    bars = js.get("bars", [])
    if not bars:
        return None

    df = pd.DataFrame(bars)
    df["t"] = pd.to_datetime(df["t"])
    df = df.sort_values("t").reset_index(drop=True)
    df = df.rename(
        columns={"t": "date", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    )
    return df[["date", "open", "high", "low", "close", "volume"]]


# ---------- analytics ----------
async def compute_scores(days_back: int = 600):
    """
    Load tickers (with optional names), fetch data, compute metrics,
    and return rows with 'name' populated from CSV or Alpaca Assets API.
    """
    # (symbol, name_from_csv?)
    ticker_pairs = load_tickers_with_names()
    symbols = [t[0] for t in ticker_pairs]

    # Date window
    end = dt.datetime.utcnow().date()
    start = end - dt.timedelta(days=int(max(380, min(days_back, 1200))))
    start_iso = f"{start.isoformat()}T00:00:00Z"
    end_iso = f"{end.isoformat()}T23:59:59Z"

    # fetch prices concurrently
    async def one_price(sym: str):
        try:
            return sym, await fetch_bars(sym, start_iso, end_iso)
        except Exception:
            return sym, None

    price_results = await asyncio.gather(*[one_price(s) for s in symbols])

    # ensure we have names (prefer CSV name; else fetch via API)
    async def one_name(sym: str, hint: str | None):
        if hint:
            NAMES_CACHE[sym] = hint
            return sym, hint
        return sym, (await fetch_company_name(sym))

    name_results = await asyncio.gather(*[one_name(sym, nm) for sym, nm in ticker_pairs])
    name_map = {sym: nm for sym, nm in name_results}

    rows: list[dict] = []
    for sym, df in price_results:
        if df is None or len(df) < 220:  # need enough history for SMA200 & 1y returns
            continue

        s = df["close"].astype(float).to_numpy()

        # SMAs
        sma50 = pd.Series(s).rolling(50).mean()
        sma200 = pd.Series(s).rolling(200).mean()
        trend_50_gt_200 = int(
            (not np.isnan(sma50.iloc[-1]))
            and (not np.isnan(sma200.iloc[-1]))
            and (sma50.iloc[-1] > sma200.iloc[-1])
        )
        ts_mom_sign = 1 if s[-1] >= (sma200.iloc[-1] if not np.isnan(sma200.iloc[-1]) else s[-1]) else -1

        # Momentum legs: 12m / 6m / 3m total returns (skip last month)
        def t_return(n: int) -> float:
            if len(s) <= n + 21:
                return np.nan
            return (s[-22] / s[-n - 22]) - 1.0

        S1 = t_return(252)   # ~12m
        S2 = t_return(126)   # ~6m
        S3 = t_return(63)    # ~3m

        # Z-score of last 60d return vs 1y daily returns
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

        rows.append({
            "symbol": sym,
            "name": name_map.get(sym),  # include company name
            "S1": float(S1) if pd.notna(S1) else None,
            "S2": float(S2) if pd.notna(S2) else None,
            "S3": float(S3) if pd.notna(S3) else None,
            "Z_mom": float(z) if pd.notna(z) else None,
            "trend50>200": trend_50_gt_200,
            "ts_mom_sign": 1 if ts_mom_sign >= 0 else -1,
            "ann_vol": ann_vol,
            "penalty": 0.0,
        })

    if not rows:
        return [], symbols, None

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

    # Simple entry rule: long-term trend + positive 6m return
    df_all["enter_long"] = ((df_all["trend50>200"] == 1) & (df_all["S2"].fillna(0) > 0)).astype(bool)

    # Breadth = share with Z_mom > 0
    valid = df_all["Z_mom"].notna()
    breadth = float((df_all.loc[valid, "Z_mom"] > 0).mean()) if valid.any() else None

    out_rows = df_all.sort_values("MomentumScore", ascending=False).to_dict(orient="records")
    return out_rows, symbols, breadth


# ---------- API endpoints ----------
@app.get("/api/scores")
async def api_scores(days_back: int = 600) -> JSONResponse:
    rows, symbols, breadth = await compute_scores(days_back=days_back)
    return JSONResponse({
        "as_of": dt.datetime.utcnow().strftime("%Y-%m-%d"),
        "breadth": breadth,
        "symbols": symbols,
        "rows": rows,
    })


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
