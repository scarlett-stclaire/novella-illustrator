#!/bin/bash
# Stops everything started by scripts/start.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for pid_file in .pids/*.pid; do
  [ -f "$pid_file" ] || continue
  name="$(basename "$pid_file" .pid)"
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "==> Stopping $name (pid $pid)"
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$pid_file"
done
