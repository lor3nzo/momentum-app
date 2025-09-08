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
+- Momentum stack: 12–1, 6–1, 3–1 (skip last month), MA50>MA200 gate, 6m TS sign, EWMA vol, breadth, composite MomentumScore + enter_long flag.
  
## Disclaimer
This project and the content provided are for educational and informational purposes only. Nothing in this repository or in the running app constitutes financial, investment, legal, tax, or other professional advice, and no content should be construed as a recommendation to buy, sell, or hold any security or financial instrument. The algorithms and information displayed are experimental and may be inaccurate or incomplete.

You should not rely on this project or the deployed website to make any investment decisions. Always do your own research and consult a licensed financial advisor before making investment choices. The creator of this project is not a registered investment advisor, broker-dealer, or securities professional, and expressly disclaims any liability for actions taken based on the information provided herein.
