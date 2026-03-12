#!/bin/bash
# ─────────────────────────────────────────────────────────
#  FlipForge — Quick Start Script
# ─────────────────────────────────────────────────────────

set -e

echo ""
echo "  ███████╗██╗     ██╗██████╗ ███████╗ ██████╗ ██████╗  ██████╗ ███████╗"
echo "  ██╔════╝██║     ██║██╔══██╗██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝"
echo "  █████╗  ██║     ██║██████╔╝█████╗  ██║   ██║██████╔╝██║  ███╗█████╗  "
echo "  ██╔══╝  ██║     ██║██╔═══╝ ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝  "
echo "  ██║     ███████╗██║██║     ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗"
echo "  ╚═╝     ╚══════╝╚═╝╚═╝     ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝"
echo ""
echo "  eBay Arbitrage Tool — Quick Start"
echo ""

# ── Check Python ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌  Python 3.10+ is required. Install from https://python.org"
  exit 1
fi

PYTHON_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_VER" -lt 10 ]; then
  echo "❌  Python 3.10+ required (found $PYTHON_MAJOR.$PYTHON_VER)"
  exit 1
fi

echo "✅  Python $PYTHON_MAJOR.$PYTHON_VER detected"

# ── Virtual environment ────────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
  echo "📦  Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

# ── Install dependencies ──────────────────────────────────────────────────────
echo "📦  Installing Python dependencies..."
echo "    (Pillow and lxml require versions compatible with your Python)"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# ── Install Playwright ────────────────────────────────────────────────────────
echo "🌐  Installing Playwright browser (Chromium)..."
playwright install chromium --with-deps

# ── Create .env ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "  ┌─────────────────────────────────────────────────────┐"
  echo "  │  ✅ .env file created with DEMO_MODE=true           │"
  echo "  │                                                     │"
  echo "  │  You can run the full app right now!                │"
  echo "  │  No eBay or Anthropic keys needed for demo mode.   │"
  echo "  │                                                     │"
  echo "  │  When ready, edit .env to add your real keys:       │"
  echo "  │    EBAY_CLIENT_ID=...                               │"
  echo "  │    EBAY_CLIENT_SECRET=...                           │"
  echo "  │    ANTHROPIC_API_KEY=...                            │"
  echo "  │    DEMO_MODE=false                                  │"
  echo "  └─────────────────────────────────────────────────────┘"
  echo ""
fi

# ── Create directories ────────────────────────────────────────────────────────
mkdir -p static/images static/processed database

echo ""
echo "✅  Setup complete! Starting server..."
echo ""
echo "  🌍  http://localhost:8000"
echo ""

python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
