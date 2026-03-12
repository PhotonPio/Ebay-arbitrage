"""
FlipForge — Configuration
All sensitive values are loaded from .env file.
DEMO_MODE=true lets you run the full app without any API keys.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).resolve().parent.parent
DB_PATH       = BASE_DIR / "database" / "listings.db"
IMAGE_DIR     = BASE_DIR / "static" / "images"
PROCESSED_DIR = BASE_DIR / "static" / "processed"

# ─── Demo Mode ───────────────────────────────────────────────────────────────
# When True: all external API calls are replaced with realistic mock data.
# Set DEMO_MODE=false in .env once you have real credentials.
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

# ─── eBay API Credentials ─────────────────────────────────────────────────────
EBAY_CLIENT_ID     = os.getenv("EBAY_CLIENT_ID", "")
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET", "")
EBAY_REDIRECT_URI  = os.getenv("EBAY_REDIRECT_URI", "http://localhost:8000/ebay/callback")
EBAY_ENV           = os.getenv("EBAY_ENV", "sandbox")   # "sandbox" | "production"

EBAY_API_BASE = (
    "https://api.ebay.com"
    if EBAY_ENV == "production"
    else "https://api.sandbox.ebay.com"
)
EBAY_AUTH_BASE = (
    "https://auth.ebay.com"
    if EBAY_ENV == "production"
    else "https://auth.sandbox.ebay.com"
)

# ─── Anthropic (Claude) ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── Pricing defaults ────────────────────────────────────────────────────────
DEFAULT_MARKUP          = float(os.getenv("DEFAULT_MARKUP", "0.80"))
MARKET_PRICE_THRESHOLD  = float(os.getenv("MARKET_PRICE_THRESHOLD", "0.20"))

# ─── Image processing ────────────────────────────────────────────────────────
EBAY_IMG_WIDTH  = 1600
EBAY_IMG_HEIGHT = 1600
JPEG_QUALITY    = 85

# ─── Shipping ────────────────────────────────────────────────────────────────
SHIPPING_MULTIPLIER = 2
DEFAULT_HANDLING    = 2

# ─── Server ──────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
