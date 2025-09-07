# Simple production image
FROM python:3.11-slim

# Install build deps only if needed by pandas/numpy (slim image)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (BACKEND + FRONTEND)
COPY backend ./backend
COPY frontend ./frontend

# Uvicorn will serve the FastAPI app
EXPOSE 8000
ENV PYTHONUNBUFFERED=1

# Start the server
# NOTE: make sure your main FastAPI app is in backend/main.py as 'app'
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
