import random
import statistics
import httpx

from config.settings import DEMO_MODE, HTTP_TIMEOUT


def _demo_market_price(retail_price: float) -> float:
    random.seed(int(retail_price * 100))
    return round(retail_price * random.uniform(0.65, 1.35), 2)


def calculate_price(retail_price: float, title: str, markup: float = 0.8, shipping_cost: float = 0.0, market_prices: list[float] | None = None):
    listing_price = round(retail_price * (1 + markup), 2)
    ebay_fee = round(listing_price * 0.1325, 2)
    paypal_fee = round(listing_price * 0.0349 + 0.49, 2)
    net_profit = round(listing_price - retail_price - ebay_fee - paypal_fee - shipping_cost, 2)
    margin_pct = round((net_profit / listing_price) * 100, 2) if listing_price else 0.0

    market_avg = None
    if DEMO_MODE:
        market_avg = _demo_market_price(retail_price)
    elif market_prices:
        market_avg = round(statistics.median(market_prices[:20]), 2)
    else:
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                _ = client.get("https://api.ebay.com")
        except Exception:
            market_avg = None

    if market_avg is not None:
        price_warning = listing_price > market_avg * 1.20
        suggested = round(market_avg * 0.97, 2)
    else:
        price_warning = False
        suggested = listing_price

    return {
        "retail_price": retail_price,
        "listing_price": listing_price,
        "ebay_fee": ebay_fee,
        "paypal_fee": paypal_fee,
        "net_profit": net_profit,
        "margin_pct": margin_pct,
        "market_avg": market_avg,
        "price_warning": price_warning,
        "suggested_price": suggested,
        "markup_pct": round(markup * 100, 2),
        "demo_mode": DEMO_MODE,
        "fees_breakdown": {"ebay": ebay_fee, "paypal": paypal_fee, "total": round(ebay_fee + paypal_fee, 2)},
    }
