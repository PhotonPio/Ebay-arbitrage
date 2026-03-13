#!/usr/bin/env bash
set -e
MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 13 ]; then
  echo "❌  Python 3.$MINOR detected. FlipForge requires Python 3.11 or 3.12."
  echo "    Install 3.12 via Homebrew: brew install python@3.12"
  echo "    Then run: python3.12 -m venv .venv"
  exit 1
fi
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium || true
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
