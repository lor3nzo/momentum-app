# Use slim Python base image
FROM python:3.11-slim

# Install build deps for pandas/numpy
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code + frontend + tickers
COPY backend ./backend
COPY frontend ./frontend
COPY tickers.csv ./tickers.csv

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
