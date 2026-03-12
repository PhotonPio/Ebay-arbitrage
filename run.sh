#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
#  ListingForge — eBay Arbitrage Tool
#  Run this script to start the application
# ──────────────────────────────────────────────────────────────────────────────

set -e

echo ""
echo "  ⚡ ListingForge — eBay Arbitrage Tool"
echo "  ─────────────────────────────────────"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "  ✗ Python 3 not found. Please install Python 3.10+"
  exit 1
fi
echo "  ✓ Python: $(python3 --version)"

# Check .env
if [ ! -f ".env" ]; then
  echo "  ⚠ No .env file found. Copying from .env.example..."
  cp .env.example .env
  echo "  → Please edit .env with your API credentials before continuing."
  echo "    See README.md for setup instructions."
  echo ""
fi

# Create virtualenv if needed
if [ ! -d "venv" ]; then
  echo "  Creating virtual environment..."
  python3 -m venv venv
fi

# Activate
source venv/bin/activate

# Install dependencies
echo "  Installing dependencies..."
pip install -r requirements.txt -q

# Install Playwright browsers if needed
if ! python3 -c "from playwright.sync_api import sync_playwright; sync_playwright().__enter__().chromium" &>/dev/null 2>&1; then
  echo "  Installing Playwright browsers (one-time setup)..."
  playwright install chromium
fi

# Create database directory
mkdir -p database
mkdir -p static/processed

echo ""
echo "  ✓ Setup complete. Starting server..."
echo "  ─────────────────────────────────────"
echo "  Open your browser: http://localhost:8000"
echo "  Dashboard:         http://localhost:8000/dashboard"
echo ""
echo "  Press Ctrl+C to stop."
echo ""

# Start the app
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
