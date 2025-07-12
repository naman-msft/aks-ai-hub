#!/usr/bin/env bash
set -e

echo "Installing Python deps…"
pip install --upgrade pip
pip install -r requirements.txt

echo "Building React frontend…"
npm install --prefix frontend
npm run build --prefix frontend

# pick up the port from Azure
PORT=${WEBSITES_PORT:-8000}
echo "Starting gunicorn on 0.0.0.0:$PORT"
exec gunicorn --bind 0.0.0.0:$PORT --timeout 600 --workers 1 app:app