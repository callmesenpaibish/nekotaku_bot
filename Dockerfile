FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create data directory for SQLite
RUN mkdir -p data

# Run as non-root
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

CMD ["python", "main.py"]
