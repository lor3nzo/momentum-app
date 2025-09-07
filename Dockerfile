# Use small Python image
FROM python:3.11-slim

# Prevents Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Workdir
WORKDIR /app

# System deps (certs, tzdata optional)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# Copy app code (backend + frontend + any data files)
COPY backend /app/backend
COPY frontend /app/frontend
COPY tickers.csv /app/tickers.csv

# Expose port Render expects
EXPOSE 8000

# Start API (serves index.html + /static/* via FastAPI)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
