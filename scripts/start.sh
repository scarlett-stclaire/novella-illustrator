#!/bin/bash
# Starts ollama, ComfyUI, the backend and the frontend natively, each as a
# background process with its own log file and pid file. Run scripts/setup.sh
# first. Stop everything with scripts/stop.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p logs .pids

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.1:8b}"

is_running() {
  local pid_file=".pids/$1.pid"
  [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null
}

start_bg() {
  local name="$1"; shift
  if is_running "$name"; then
    echo "==> $name already running (pid $(cat .pids/$name.pid))"
    return
  fi
  echo "==> Starting $name"
  ( "$@" > "logs/$name.log" 2>&1 & echo $! > ".pids/$name.pid" )
}

if command -v curl >/dev/null 2>&1 && curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "==> ollama already running (not managed by this script)"
else
  start_bg ollama ollama serve
  echo "==> Waiting for ollama..."
  until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do sleep 1; done
fi

echo "==> Ensuring model '$OLLAMA_MODEL' is pulled (no-op if already present)"
ollama pull "$OLLAMA_MODEL" || echo "WARNING: failed to pull $OLLAMA_MODEL"

start_bg comfyui comfyui/src/ComfyUI/.venv/bin/python comfyui/src/ComfyUI/main.py \
  --listen 127.0.0.1 --port 8188

start_bg backend backend/.venv/bin/uvicorn app.main:app \
  --app-dir backend --reload --reload-dir backend/app --host 127.0.0.1 --port 8000

start_bg frontend npm --prefix frontend run dev

cat <<EOF

Stack starting up. Logs in ./logs/, pids in ./.pids/.
  frontend: http://localhost:3000
  backend:  http://localhost:8000
  comfyui:  http://localhost:8188
  ollama:   http://localhost:11434

Run scripts/stop.sh to stop everything.
EOF
