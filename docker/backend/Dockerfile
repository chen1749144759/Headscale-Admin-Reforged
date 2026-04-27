FROM python:3.13-slim

WORKDIR /app

# 系统依赖（psycopg2-binary 需要 libpq）
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 层缓存
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# 复制后端代码
COPY api/ ./api/

EXPOSE 5175

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "5175"]
