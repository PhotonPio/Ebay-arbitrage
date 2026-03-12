"""
Pricing Engine
Calculates listing price and checks against eBay market averages.
In DEMO_MODE, returns realistic mock market prices without any API calls.
"""
import random
import sys
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    DEFAULT_MARKUP, MARKET_PRICE_THRESHOLD,
    EBAY_API_BASE, EBAY_CLIENT_ID, EBAY_CLIENT_SECRET,
    DEMO_MODE,
)


# ── Demo mock market prices ───────────────────────────────────────────────────

def _mock_market_price(retail_price: float) -> float:
    """
    Simulate a realistic eBay market price.
    Real eBay prices cluster between 0.6x–1.3x retail depending on category.
    """
    # Seed randomness from price so same product always returns same mock value
    rng = random.Random(int(retail_price * 100))
    multiplier = rng.uniform(0.65, 1.25)
    return round(retail_price * multiplier, 2)


# ── eBay Browse API token (client credentials) ───────────────────────────────

_token_cache: dict = {"token": None, "expires_at": 0}


def _get_app_token() -> str:
    import time, base64
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 30:
        return _token_cache["token"]

    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        return ""

    creds = base64.b64encode(f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()).decode()
    try:
        resp = httpx.post(
            f"{EBAY_API_BASE}/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=10,
        )
        data = resp.json()
        _token_cache["token"] = data.get("access_token", "")
        _token_cache["expires_at"] = time.time() + int(data.get("expires_in", 7200))
        return _token_cache["token"]
    except Exception as e:
        print(f"⚠ eBay token error: {e}")
        return ""


# ── Market price lookup ───────────────────────────────────────────────────────

def fetch_market_avg_price(query: str, retail_price: float = 0.0) -> Optional[float]:
    """
    Fetch average eBay market price for a search term.
    Returns mock data in DEMO_MODE; calls live API otherwise.
    """
    if DEMO_MODE:
        if retail_price > 0:
            return _mock_market_price(retail_price)
        return None

    token = _get_app_token()
    if not token or not query:
        return None

    try:
        resp = httpx.get(
            f"{EBAY_API_BASE}/buy/browse/v1/item_summary/search",
            params={
                "q": query[:100],
                "limit": 20,
                "sort": "BEST_MATCH",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
            timeout=10,
        )
        data = resp.json()
        items = data.get("itemSummaries", [])
        prices = []
        for item in items:
            price_obj = item.get("price", {})
            try:
                prices.append(float(price_obj.get("value", 0)))
            except (ValueError, TypeError):
                pass
        if prices:
            return round(sum(prices) / len(prices), 2)
    except Exception as e:
        print(f"⚠ eBay Browse API error: {e}")

    return None


# ── Pricing calculation ───────────────────────────────────────────────────────

def calculate_price(
    retail_price: float,
    title: str,
    markup: float = DEFAULT_MARKUP,
) -> dict:
    """
    Returns a full pricing breakdown dict.
    Works in both demo and live mode.
    """
    listing_price = round(retail_price * (1 + markup), 2)

    # Fetch (or mock) market average
    market_avg = fetch_market_avg_price(title, retail_price)

    warning = False
    suggested_price = listing_price

    if market_avg and market_avg > 0:
        overage = (listing_price - market_avg) / market_avg
        if overage > MARKET_PRICE_THRESHOLD:
            warning = True
            suggested_price = round(market_avg * 0.97, 2)

    margin_pct = round(((listing_price - retail_price) / listing_price) * 100, 1)

    return {
        "listing_price": listing_price,
        "market_avg": market_avg,
        "warning": warning,
        "suggested_price": suggested_price,
        "markup_pct": round(markup * 100, 1),
        "margin_pct": margin_pct,
        "demo_mode": DEMO_MODE,
    }
