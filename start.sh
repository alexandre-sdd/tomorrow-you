#!/usr/bin/env bash
# start.sh — launch backend + frontend in parallel

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Ensure storage directory exists (required for FastAPI static file mount)
mkdir -p "$ROOT/storage/sessions"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

echo -e "${CYAN}Tomorrow You — starting...${RESET}"
echo ""

# --- Python deps ---
echo -e "${YELLOW}[backend]${RESET} Installing Python dependencies..."
pip install -r "$ROOT/requirements.txt" -q

# --- Frontend deps ---
if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo -e "${YELLOW}[frontend]${RESET} node_modules not found — running npm install..."
  cd "$ROOT/frontend" && npm install
fi

# --- Backend (run from project root so backend.* imports resolve) ---
echo -e "${YELLOW}[backend]${RESET} Starting FastAPI on http://localhost:8000"
cd "$ROOT"
python -m uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

# --- Frontend ---
echo -e "${YELLOW}[frontend]${RESET} Starting Next.js on http://localhost:3000"
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}Both services running.${RESET}"
echo -e "  Backend:  http://localhost:8000/docs"
echo -e "  Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both."

# Trap Ctrl+C and kill both processes
cleanup() {
  echo ""
  echo "Stopping..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
  echo "Done."
}
trap cleanup INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
