#!/usr/bin/env bash
# SiteSync AI — development quick-start
# Usage: ./dev.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "▶  Starting SiteSync AI development environment"
echo ""

# Backend
echo "[backend] Starting FastAPI on http://localhost:8000"
cd "$ROOT_DIR/backend"
if [ ! -d ".venv" ]; then
  echo "[backend] Creating virtual environment…"
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt
fi
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Frontend
echo "[frontend] Starting Vite on http://localhost:3000"
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!


echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  API docs: http://localhost:8000/docs  (development only)"
echo ""
echo "Press Ctrl+C to stop both servers."

# Wait for both; kill both on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
