#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -e .
echo "GEOточка запущена: http://127.0.0.1:8000"
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
