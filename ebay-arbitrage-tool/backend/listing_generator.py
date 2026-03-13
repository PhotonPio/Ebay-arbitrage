import re
from html import escape
from anthropic import Anthropic
from config.settings import ANTHROPIC_API_KEY


def _truncate(text: str, n: int = 80) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    return cut[: cut.rfind(' ')] if ' ' in cut else cut


def generate_ebay_title(raw_title: str, brand: str, specs: dict) -> str:
    spec_str = ", ".join([str(v) for v in list((specs or {}).values())[:3]])
    if ANTHROPIC_API_KEY:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt = (
            "System: You are an eBay SEO specialist. Rules: max 80 chars, no ALL CAPS words, "
            "include brand + product type + 2-3 key specs + condition keyword, prioritize searchable terms over marketing language.\n"
            f"User: Brand: {brand}, Title: {raw_title}, Top specs: {spec_str}\n"
            "Return ONLY the optimized title. Nothing else."
        )
        for _ in range(2):
            try:
                msg = client.messages.create(model="claude-3-5-sonnet-latest", max_tokens=120, messages=[{"role": "user", "content": prompt}])
                out = str(msg.content[0].text).strip().strip('"').replace('Title:', '').strip()
                if 20 <= len(out) <= 80:
                    return out
            except Exception:
                break

    title = raw_title or "Product"
    if brand and brand.lower() not in title.lower():
        title = f"{brand} {title}"
    title = re.sub(r"\b(New|Free Shipping)\b", "", title, flags=re.I)
    title = re.sub(r"\|.*$", "", title).strip()
    title = re.sub(r"\s+-\s*$", "", title)
    extra = " ".join([str(v) for v in list((specs or {}).values())[:2]])
    if extra and len(title) + len(extra) + 1 <= 75:
        title = f"{title} {extra}"
    return _truncate(title, 80) or _truncate(raw_title or "Product", 80)


def _spec_table(specs: dict) -> str:
    rows = "".join([f"<tr><td>{escape(str(k))}</td><td>{escape(str(v))}</td></tr>" for k, v in (specs or {}).items()])
    return f"<table>{rows}</table>"


def generate_ebay_description(title: str, brand: str, raw_description: str, specs: dict, shipping_days: int, handling_days: int) -> str:
    if ANTHROPIC_API_KEY:
        try:
            client = Anthropic(api_key=ANTHROPIC_API_KEY)
            prompt = f"Generate HTML sections exactly: Product Overview, Key Features, Technical Specifications, Shipping & Handling, Seller Guarantee. Title={title}, Brand={brand}, Description={raw_description}, Specs={specs}, Shipping={shipping_days}, Handling={handling_days}."
            msg = client.messages.create(model="claude-3-5-sonnet-latest", max_tokens=900, messages=[{"role": "user", "content": prompt}])
            html = str(msg.content[0].text)
            if all(h in html for h in ["Product Overview", "Key Features", "Technical Specifications", "Shipping & Handling", "Seller Guarantee"]):
                return html
        except Exception:
            pass

    features = "".join([f"<li>✔ {escape(line.strip())}</li>" for line in raw_description.splitlines()[:8] if line.strip()])
    return f"""
    <h3>Product Overview</h3><p>{escape(raw_description[:400] or title)}</p>
    <h3>Key Features</h3><ul>{features}</ul>
    <h3>Technical Specifications</h3>{_spec_table(specs)}
    <h3>Shipping & Handling</h3><p>Ships in {shipping_days} business days. Handling: {handling_days} day(s).</p>
    <h3>Seller Guarantee</h3><p>Secure packaging, quick response support, and returns support as applicable.</p>
    """.strip()


def calculate_quality_score(title: str, description: str, images: list[str], price: float | None, market_avg: float | None, specs: dict):
    score = {"title": 0, "description": 0, "images": 0, "price": 0, "specs": 0}
    tips = []
    if 40 <= len(title) <= 80:
        score["title"] += 10
    if len(title.split()) >= 5:
        score["title"] += 5
    if any(w in title.lower() for w in ["new", "free shipping"]):
        tips.append("Remove fluff words from title.")
    else:
        score["title"] += 10

    sections = ["Product Overview", "Key Features", "Technical Specifications", "Shipping & Handling", "Seller Guarantee"]
    if all(s in description for s in sections):
        score["description"] += 15
    if len(re.sub(r"<[^>]+>", "", description).split()) > 150:
        score["description"] += 5

    score["images"] = min(len(images), 5) * 5

    if price and market_avg:
        delta = abs(price - market_avg) / market_avg
        score["price"] = 20 if delta <= 0.15 else 15 if delta <= 0.25 else 8
    elif price:
        score["price"] = 8

    score["specs"] = min(len(specs), 5) * 2
    total = sum(score.values())
    grade = "A" if total >= 85 else "B" if total >= 70 else "C" if total >= 55 else "D" if total >= 40 else "F"
    if len(images) < 5:
        tips.append("Add more product images.")
    return {"total": total, "breakdown": score, "grade": grade, "improvement_tips": tips}
