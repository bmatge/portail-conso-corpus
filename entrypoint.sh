#!/usr/bin/env bash
set -e

echo "[entrypoint] Starting nginx..."
nginx

echo "[entrypoint] Starting FastAPI on port 8000..."
exec uvicorn api.search_api:app --host 0.0.0.0 --port 8000 --log-level info --app-dir /app
