"""
Listing Generator — uses Claude (Anthropic) to create optimised eBay listings.
Falls back to a rule-based generator if no API key is configured.
"""
import re
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import ANTHROPIC_API_KEY


# ── AI-powered generation ────────────────────────────────────────────────────

def _call_claude(prompt: str) -> str:
    """Call Anthropic API and return text response."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def generate_ebay_title(raw_title: str, brand: str, specs: dict) -> str:
    """Generate an eBay-optimised title (max 80 chars)."""
    spec_str = ", ".join(f"{k}: {v}" for k, v in list(specs.items())[:5])
    if ANTHROPIC_API_KEY:
        prompt = (
            f"You are an eBay SEO expert. Create a single optimized eBay product title "
            f"that maximizes keyword coverage and visibility. Max 80 characters. "
            f"No special characters except hyphen and pipe. No generic filler words.\n\n"
            f"Product title: {raw_title}\n"
            f"Brand: {brand}\n"
            f"Key specs: {spec_str}\n\n"
            f"Return ONLY the title, nothing else."
        )
        try:
            title = _call_claude(prompt)
            return title[:80]
        except Exception as e:
            print(f"⚠ Claude title error: {e}")

    # ── Rule-based fallback ──────────────────────────────────────────────────
    parts = []
    if brand and brand.lower() not in raw_title.lower():
        parts.append(brand)
    parts.append(raw_title)
    combined = " ".join(parts)
    # Remove fluff
    for word in ["the", "a", "an", "and", "with", "for", "new", "-", "|"]:
        combined = re.sub(rf'\b{re.escape(word)}\b', " ", combined, flags=re.I)
    combined = re.sub(r'\s+', " ", combined).strip()
    return combined[:80]


def generate_ebay_description(
    title: str,
    brand: str,
    raw_description: str,
    specs: dict,
    shipping_days: int,
    handling_days: int,
) -> str:
    """Generate a marketplace-friendly HTML description."""
    spec_lines = "\n".join(f"- {k}: {v}" for k, v in specs.items())
    if ANTHROPIC_API_KEY:
        prompt = (
            f"You are an expert eBay listing copywriter. Write a compelling, "
            f"conversion-focused eBay listing description in clean HTML. "
            f"Use this structure:\n"
            f"1. Product Overview (2–3 sentences)\n"
            f"2. Key Features (5–7 bullet points starting with ✔)\n"
            f"3. Specifications (as a clean table)\n"
            f"4. Shipping Information (mention {shipping_days} day shipping, "
            f"{handling_days} day handling)\n\n"
            f"Product: {title}\nBrand: {brand}\n"
            f"Description: {raw_description[:800]}\n"
            f"Specs:\n{spec_lines}\n\n"
            f"Return ONLY the HTML body content. No markdown. No code fences. "
            f"Use inline styles for a clean, professional look."
        )
        try:
            return _call_claude(prompt)
        except Exception as e:
            print(f"⚠ Claude description error: {e}")

    # ── Rule-based fallback ──────────────────────────────────────────────────
    bullets = []
    if brand:
        bullets.append(f"✔ Authentic {brand} product")
    if raw_description:
        # Extract sentences as bullets
        sentences = re.split(r'[.!]\s+', raw_description)
        for s in sentences[:5]:
            s = s.strip()
            if len(s) > 20:
                bullets.append(f"✔ {s}")

    spec_rows = "".join(
        f"<tr><td style='padding:4px 8px;font-weight:600'>{k}</td>"
        f"<td style='padding:4px 8px'>{v}</td></tr>"
        for k, v in specs.items()
    )

    bullet_html = "".join(f"<li style='margin:4px 0'>{b}</li>" for b in bullets)

    return f"""
<div style="font-family:Arial,sans-serif;max-width:800px;color:#222;line-height:1.6">

  <h2 style="color:#0064d2;border-bottom:2px solid #0064d2;padding-bottom:8px">
    Product Overview
  </h2>
  <p>{raw_description[:400] if raw_description else 'High-quality product from a trusted brand.'}</p>

  <h2 style="color:#0064d2;border-bottom:2px solid #0064d2;padding-bottom:8px;margin-top:24px">
    Key Features
  </h2>
  <ul style="list-style:none;padding:0">{bullet_html}</ul>

  <h2 style="color:#0064d2;border-bottom:2px solid #0064d2;padding-bottom:8px;margin-top:24px">
    Specifications
  </h2>
  <table style="width:100%;border-collapse:collapse">
    <tbody>{spec_rows}</tbody>
  </table>

  <h2 style="color:#0064d2;border-bottom:2px solid #0064d2;padding-bottom:8px;margin-top:24px">
    Shipping Information
  </h2>
  <p>
    📦 Estimated delivery: <strong>{shipping_days} business days</strong><br>
    🕐 Handling time: <strong>{handling_days} days</strong><br>
    All items are carefully packaged to ensure safe arrival.
  </p>

</div>
"""


# ── Quality Score ─────────────────────────────────────────────────────────────

def calculate_quality_score(
    title: str,
    description: str,
    images: list,
    price: float,
    market_avg: float | None,
    specs: dict,
) -> dict:
    """
    Score from 0–100 across four dimensions.
    Returns dict with total and breakdown.
    """
    # Title (max 30 pts)
    title_score = 0
    if title:
        words = len(title.split())
        title_score += min(words * 2, 15)          # keyword coverage
        title_score += 10 if len(title) >= 40 else 5  # length
        title_score += 5 if len(title) <= 80 else 0   # within limit

    # Description (max 25 pts)
    desc_score = 0
    if description:
        desc_score += min(len(description) // 100, 15)   # length proxy
        for kw in ["feature", "spec", "ship", "quality", "brand"]:
            if kw in description.lower():
                desc_score += 2
        desc_score = min(desc_score, 25)

    # Images (max 25 pts)
    img_count  = len(images)
    img_score  = min(img_count * 5, 25)

    # Price (max 20 pts)
    price_score = 20
    if market_avg and market_avg > 0 and price:
        diff = abs(price - market_avg) / market_avg
        if diff > 0.20:
            price_score = max(0, 20 - int(diff * 50))

    total = title_score + desc_score + img_score + price_score

    return {
        "total": min(total, 100),
        "title": title_score,
        "description": desc_score,
        "images": img_score,
        "price": price_score,
        "grade": (
            "A" if total >= 85 else
            "B" if total >= 70 else
            "C" if total >= 55 else
            "D"
        ),
    }
