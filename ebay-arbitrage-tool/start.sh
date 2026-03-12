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

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "❌  Python 3.10+ is required. Install from https://python.org"
  exit 1
fi

PYTHON_VER=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_VER" -lt 10 ]; then
  echo "❌  Python 3.10+ required (found 3.$PYTHON_VER)"
  exit 1
fi

# Create venv
if [ ! -d ".venv" ]; then
  echo "📦  Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate
source .venv/bin/activate

# Install dependencies
echo "📦  Installing Python dependencies..."
pip install -q -r requirements.txt

# Install Playwright browsers
echo "🌐  Installing Playwright browser (Chromium)..."
playwright install chromium --with-deps

# Create .env from example if not exists
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "⚠   Created .env file. Please edit it with your API credentials before running."
  echo "    → Open .env and add your EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, ANTHROPIC_API_KEY"
  echo ""
fi

# Create directories
mkdir -p static/images static/processed database

echo ""
echo "✅  Setup complete! Starting server..."
echo ""
echo "  🌍  http://localhost:8000"
echo ""

# Start server
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
