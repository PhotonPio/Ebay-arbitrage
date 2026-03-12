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
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" &>/dev/null; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "❌  Python 3.10+ is required. Install from https://python.org"
  exit 1
fi

PYTHON_MAJOR=$($PYTHON_BIN -c "import sys; print(sys.version_info.major)")
PYTHON_VER=$($PYTHON_BIN -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_VER" -lt 10 ]; then
  echo "❌  Python 3.10+ required (found $PYTHON_MAJOR.$PYTHON_VER)"
  exit 1
fi

echo "✅  Using $PYTHON_BIN ($PYTHON_MAJOR.$PYTHON_VER)"

# ── Virtual environment ────────────────────────────────────────────────────────
if [ -d ".venv" ]; then
  VENV_PY_MAJOR=$(.venv/bin/python -c "import sys; print(sys.version_info.major)")
  VENV_PY_MINOR=$(.venv/bin/python -c "import sys; print(sys.version_info.minor)")
  if [ "$VENV_PY_MAJOR" -ne "$PYTHON_MAJOR" ] || [ "$VENV_PY_MINOR" -ne "$PYTHON_VER" ]; then
    echo "🧹  Recreating virtual environment for $PYTHON_BIN..."
    rm -rf .venv
  fi
fi

if [ ! -d ".venv" ]; then
  echo "📦  Creating virtual environment..."
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

# ── Install dependencies ──────────────────────────────────────────────────────
echo "📦  Installing Python dependencies..."
echo "    (Pillow and lxml require versions compatible with your Python)"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# ── Install Playwright ────────────────────────────────────────────────────────
echo "🌐  Installing Playwright browser (Chromium)..."
OS_NAME="$(uname -s)"
if [ "$OS_NAME" = "Linux" ]; then
  playwright install chromium --with-deps
else
  playwright install chromium
fi

# ── Create .env ───────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
  elif [ -f "flipforge/.env.example" ]; then
    cp flipforge/.env.example .env
  else
    cat > .env <<'EOF'
DEMO_MODE=true
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_REDIRECT_URI=http://localhost:8000/ebay/callback
EBAY_ENV=sandbox
ANTHROPIC_API_KEY=
DEFAULT_MARKUP=0.80
MARKET_PRICE_THRESHOLD=0.20
HOST=0.0.0.0
PORT=8000
EOF
  fi
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
