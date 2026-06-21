FROM python:3.13-slim

WORKDIR /app

# Runtime dependencies for health checks and PostgreSQL clients.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to keep Docker layer cache useful.
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy backend source.
COPY api/ ./api/

EXPOSE 5175

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "5175"]
