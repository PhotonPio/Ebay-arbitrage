"""
backend/pricing_engine.py
Calculates listing price and checks eBay market for competitiveness.
"""
import httpx
import logging
import re
from typing import Optional, Dict, List
import base64

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PricingEngine:
    """Computes listing price and validates against eBay market."""

    def calculate_listing_price(self, raw_price: float, markup: float = 0.80) -> float:
        """listing_price = raw_price × (1 + markup)"""
        return round(raw_price * (1 + markup), 2)

    async def check_market_price(self, title: str, your_price: float) -> Dict:
        """
        Query eBay Browse API to get market average for comparison.
        Returns price check result dict.
        """
        if not settings.ebay_active_app_id:
            return self._no_api_result(your_price)

        # Get OAuth token for Browse API
        token = await self._get_browse_token()
        if not token:
            return self._no_api_result(your_price)

        try:
            # Clean search query
            query = re.sub(r"[^\w\s]", "", title)[:100].strip()
            url = f"{settings.ebay_base_url}/buy/browse/v1/item_summary/search"
            params = {
                "q": query,
                "limit": "20",
                "filter": "buyingOptions:{FIXED_PRICE},conditions:{NEW}",
                "sort": "price"
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    logger.warning(f"eBay Browse API: {resp.status_code} {resp.text[:200]}")
                    return self._no_api_result(your_price)

                data = resp.json()
                items = data.get("itemSummaries", [])
                if not items:
                    return self._no_api_result(your_price)

                prices = []
                for item in items:
                    price_obj = item.get("price", {})
                    try:
                        prices.append(float(price_obj.get("value", 0)))
                    except (ValueError, TypeError):
                        pass

                prices = [p for p in prices if p > 0]
                if not prices:
                    return self._no_api_result(your_price)

                market_avg = round(sum(prices) / len(prices), 2)
                market_min = round(min(prices), 2)
                market_max = round(max(prices), 2)

                threshold = settings.price_warning_threshold
                warning = your_price > market_avg * (1 + threshold)
                suggested_price = round(market_avg * 0.95, 2) if warning else None

                if warning:
                    message = (
                        f"⚠ Your price (${your_price:.2f}) exceeds market average "
                        f"(${market_avg:.2f}) by more than {int(threshold*100)}%. "
                        f"Suggested competitive price: ${suggested_price:.2f}"
                    )
                else:
                    message = (
                        f"✓ Your price (${your_price:.2f}) is competitive. "
                        f"Market average: ${market_avg:.2f} ({len(prices)} listings)"
                    )

                return {
                    "market_avg": market_avg,
                    "market_min": market_min,
                    "market_max": market_max,
                    "sample_count": len(prices),
                    "your_price": your_price,
                    "warning": warning,
                    "suggested_price": suggested_price,
                    "message": message,
                }

        except Exception as e:
            logger.error(f"Market price check error: {e}")
            return self._no_api_result(your_price)

    async def _get_browse_token(self) -> Optional[str]:
        """Get OAuth client credentials token for Browse API."""
        app_id = settings.ebay_active_app_id
        cert_id = settings.ebay_active_cert_id
        if not app_id or not cert_id:
            return None

        credentials = base64.b64encode(f"{app_id}:{cert_id}".encode()).decode()
        token_url = (
            "https://api.ebay.com/identity/v1/oauth2/token"
            if settings.ebay_environment == "production"
            else "https://api.sandbox.ebay.com/identity/v1/oauth2/token"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    token_url,
                    headers={
                        "Authorization": f"Basic {credentials}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={
                        "grant_type": "client_credentials",
                        "scope": "https://api.ebay.com/oauth/api_scope",
                    }
                )
                if resp.status_code == 200:
                    return resp.json().get("access_token")
        except Exception as e:
            logger.error(f"OAuth token error: {e}")
        return None

    def _no_api_result(self, your_price: float) -> Dict:
        """Return a neutral result when eBay API is unavailable."""
        return {
            "market_avg": None,
            "market_min": None,
            "market_max": None,
            "sample_count": 0,
            "your_price": your_price,
            "warning": False,
            "suggested_price": None,
            "message": "ℹ Market price check unavailable (eBay API not configured). Price set based on markup formula.",
        }

    def calculate_profit(self, raw_price: float, listing_price: float) -> Dict:
        """Calculate profit amount and margin."""
        profit_amount = round(listing_price - raw_price, 2)
        profit_margin = round((profit_amount / listing_price) * 100, 1) if listing_price > 0 else 0
        return {
            "profit_amount": profit_amount,
            "profit_margin": profit_margin,
        }
