FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-mysql-server \
    default-mysql-client \
    build-essential \
    curl \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Copy app files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make shell script executable
RUN chmod +x start.sh

# Expose MySQL default port (optional if needed externally)
EXPOSE 3306

# Use shell script as entrypoint
CMD ["./start.sh"]
