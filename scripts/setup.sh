#!/bin/bash
# One-time (or re-run-anytime) environment setup for running the stack
# natively on macOS. Rebuilds everything EXCEPT comfyui/models/ - those
# FLUX weight files are the one thing worth copying between machines
# instead of re-downloading; everything else here is disposable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.13 || command -v python3)}"

echo "==> Using python: $PYTHON_BIN ($($PYTHON_BIN --version))"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env from .env.example"
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "==> Installing ollama"
  brew install ollama
else
  echo "==> ollama already installed ($(ollama --version))"
fi

if ! command -v node >/dev/null 2>&1; then
  echo "==> Installing node"
  brew install node
else
  echo "==> node already installed ($(node --version))"
fi

echo "==> Setting up backend venv"
if [ ! -d backend/.venv ]; then
  "$PYTHON_BIN" -m venv backend/.venv
fi
backend/.venv/bin/pip install --quiet --upgrade pip
backend/.venv/bin/pip install --quiet -r backend/requirements.txt

echo "==> Installing frontend dependencies"
(cd frontend && npm install --silent)

echo "==> Setting up ComfyUI"
mkdir -p comfyui/src
if [ ! -d comfyui/src/ComfyUI ]; then
  git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git comfyui/src/ComfyUI
fi
if [ ! -d comfyui/src/ComfyUI/.venv ]; then
  "$PYTHON_BIN" -m venv comfyui/src/ComfyUI/.venv
fi
comfyui/src/ComfyUI/.venv/bin/pip install --quiet --upgrade pip
# Plain `pip install torch` on macOS arm64 ships MPS (Metal) support already -
# no CUDA index or extra flags needed.
comfyui/src/ComfyUI/.venv/bin/pip install --quiet -r comfyui/src/ComfyUI/requirements.txt

echo "==> Linking persistent models/output into the ComfyUI checkout"
rm -rf comfyui/src/ComfyUI/models comfyui/src/ComfyUI/output
ln -sfn "$ROOT/comfyui/models" comfyui/src/ComfyUI/models
ln -sfn "$ROOT/comfyui/output" comfyui/src/ComfyUI/output

echo "==> Setup complete. Run scripts/start.sh to launch the stack."
