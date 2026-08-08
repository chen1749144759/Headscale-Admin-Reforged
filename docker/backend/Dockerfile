FROM python:3.13-slim

WORKDIR /app

# Runtime dependencies for health checks and PostgreSQL clients.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl gosu && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10101 scaleforge && \
    useradd --uid 10001 --gid 10101 --no-create-home --shell /usr/sbin/nologin scaleforge

# Copy requirements first to keep Docker layer cache useful.
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy backend source.
COPY api/ ./api/
COPY migrations/ ./migrations/
COPY docker/backend/entrypoint.sh /usr/local/bin/scaleforge-backend
RUN chmod 0755 /usr/local/bin/scaleforge-backend

CMD ["/usr/local/bin/scaleforge-backend"]
