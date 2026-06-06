# LinkShortify Bot v2.0 — MongoDB/Motor (no local database needed)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY run.py .
COPY app ./app

# Run the bot (long-polling; connects to MongoDB Atlas via MONGODB_URI)
CMD ["python", "run.py"]
