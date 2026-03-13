import re
from bs4 import BeautifulSoup
import httpx

from backend.database import ScannerResult, ScannerTarget
from backend.pricing_engine import calculate_price
from backend.vero_checker import check_brand
from config.settings import HTTP_TIMEOUT


def _extract_cards(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for card in soup.select("a,article,div")[:80]:
        text = card.get_text(" ", strip=True)
        if not text:
            continue
        m = re.search(r"\$\s*([\d,.]+)", text)
        if not m:
            continue
        name = text[:80]
        href = card.get("href") if hasattr(card, "get") else None
        img = card.select_one("img")
        img_url = img.get("src") if img else ""
        items.append({"product_name": name, "retail_price": float(m.group(1).replace(',', '')), "retail_url": href or base_url, "image_url": img_url})
        if len(items) >= 20:
            break
    return items


def scan_target(db, target: ScannerTarget):
    try:
        html = httpx.get(target.url, timeout=HTTP_TIMEOUT, follow_redirects=True).text
    except Exception:
        html = ""
    products = _extract_cards(html, target.url)
    results = []
    for p in products:
        pricing = calculate_price(p["retail_price"], p["product_name"], 0.8)
        market = pricing.get("market_avg")
        margin = ((market - p["retail_price"]) / p["retail_price"] * 100) if market else 0
        risk = check_brand(target.brand)["risk_level"]
        row = ScannerResult(
            brand=target.brand,
            product_name=p["product_name"],
            retail_price=p["retail_price"],
            retail_url=p["retail_url"],
            image_url=p["image_url"],
            market_avg_price=market,
            profit_margin_pct=margin,
            is_opportunity=bool(market and margin > 20),
            vero_risk_level=risk,
        )
        db.add(row)
        results.append(row)
    db.commit()
    return results


def scan_all_targets(db):
    out = []
    for t in db.query(ScannerTarget).filter(ScannerTarget.enabled == True).all():
        out.extend(scan_target(db, t))
    return out
