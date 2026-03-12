"""
Pricing Engine
Calculates listing price and checks against eBay market averages.
"""
import sys
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    DEFAULT_MARKUP, MARKET_PRICE_THRESHOLD,
    EBAY_API_BASE, EBAY_CLIENT_ID, EBAY_CLIENT_SECRET,
)


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
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
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

def fetch_market_avg_price(query: str) -> Optional[float]:
    """
    Use eBay Browse API to find average sold/listed price for a search term.
    Returns None if credentials are missing or API fails.
    """
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
    Returns a pricing result dict:
    {
        listing_price, market_avg, warning, suggested_price, margin_pct
    }
    """
    listing_price = round(retail_price * (1 + markup), 2)

    # Check market
    market_avg = fetch_market_avg_price(title)

    warning = False
    suggested_price = listing_price

    if market_avg and market_avg > 0:
        overage = (listing_price - market_avg) / market_avg
        if overage > MARKET_PRICE_THRESHOLD:
            warning = True
            # Suggest just under the market avg to stay competitive
            suggested_price = round(market_avg * 0.97, 2)

    margin_pct = round(((listing_price - retail_price) / listing_price) * 100, 1)

    return {
        "listing_price": listing_price,
        "market_avg": market_avg,
        "warning": warning,
        "suggested_price": suggested_price,
        "markup_pct": round(markup * 100, 1),
        "margin_pct": margin_pct,
    }
