# Momentum Meter (Alpaca) — FastAPI + Vanilla JS

Server-side calls to **Alpaca Market Data v2** using your API keys; simple frontend renders the momentum dashboard.

## Quickstart

### Local (no Docker)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then edit with your Alpaca keys
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Visit http://localhost:8000

### Docker
```bash
docker build -t momentum-app .
docker run -p 8000:8000 --env-file .env -v $(pwd)/tickers.csv:/app/tickers.csv:ro momentum-app
```

## Configure symbols
Edit `tickers.csv` (single column header `symbol`). Refresh page to refetch.

## Notes
- Uses **raw** close bars (`adjustment=raw`) with `feed=iex`. Consider adjusted/total-return series for production.
- Earnings blackout not included (separate provider needed).
- Momentum stack: 12–1, 6–1, 3–1 (skip last month), MA50>MA200 gate, 6m TS sign, EWMA vol, breadth, composite MomentumScore + enter_long flag.
