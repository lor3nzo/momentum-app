WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code AND the tickers file
COPY backend ./backend
COPY frontend ./frontend
COPY tickers.csv ./tickers.csv    # ← add this line

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
