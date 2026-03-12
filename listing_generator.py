"""
Listing Generator
Uses Claude AI if ANTHROPIC_API_KEY is set; otherwise uses a high-quality
rule-based generator that works completely offline.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import ANTHROPIC_API_KEY, DEMO_MODE


# ── AI-powered generation ────────────────────────────────────────────────────

def _call_claude(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


# ── Title generator ──────────────────────────────────────────────────────────

def generate_ebay_title(raw_title: str, brand: str, specs: dict) -> str:
    """Generate an eBay-optimised title (max 80 chars)."""
    spec_str = ", ".join(f"{k}: {v}" for k, v in list(specs.items())[:5])

    if ANTHROPIC_API_KEY and not DEMO_MODE:
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
            return _call_claude(prompt)[:80]
        except Exception as e:
            print(f"⚠ Claude title error: {e}")

    # ── High-quality rule-based generator ───────────────────────────────────
    parts = []

    # Brand first if not already in title
    if brand and brand.strip() and brand.lower() not in raw_title.lower():
        parts.append(brand.strip())

    # Clean the raw title
    cleaned = raw_title.strip()
    # Remove common retail fluff
    fluff = [
        r'\s*\|.*$',           # everything after pipe
        r'\s*-\s*[A-Z][^-]+$', # trailing brand suffix
        r'\bNew\b', r'\bBrand\b', r'\bOEM\b',
        r'\bFree Shipping\b', r'\bFast Ship\b',
    ]
    for pattern in fluff:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    parts.append(cleaned)

    # Add top spec keywords if space allows
    for k, v in list(specs.items())[:3]:
        candidate = f"{v}"
        combined = " ".join(parts + [candidate])
        if len(combined) <= 75:
            parts.append(candidate)
        else:
            break

    title = " ".join(parts)
    return title[:80]


# ── Description generator ────────────────────────────────────────────────────

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

    if ANTHROPIC_API_KEY and not DEMO_MODE:
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
            f"Return ONLY the HTML body content. No markdown. No code fences."
        )
        try:
            return _call_claude(prompt)
        except Exception as e:
            print(f"⚠ Claude description error: {e}")

    # ── High-quality rule-based fallback ────────────────────────────────────
    bullets = []
    if brand:
        bullets.append(f"✔ Authentic <strong>{brand}</strong> product — quality guaranteed")

    if raw_description:
        sentences = re.split(r'(?<=[.!?])\s+', raw_description)
        for s in sentences[:6]:
            s = s.strip()
            if len(s) > 20 and not any(skip in s.lower() for skip in ['javascript', 'cookie', 'cart']):
                bullets.append(f"✔ {s}")

    if not bullets:
        bullets = [
            "✔ Brand new, unopened in original packaging",
            "✔ Ships fast — carefully packed for safe delivery",
            "✔ Satisfaction guaranteed — contact us with any questions",
        ]

    spec_rows = "".join(
        f"<tr style='border-bottom:1px solid #eee'>"
        f"<td style='padding:8px 12px;font-weight:600;background:#f8f9fa;width:40%'>{k}</td>"
        f"<td style='padding:8px 12px'>{v}</td></tr>"
        for k, v in specs.items()
    ) if specs else "<tr><td colspan='2' style='padding:8px'>See product images for details</td></tr>"

    bullet_html = "".join(f"<li style='margin:6px 0;line-height:1.5'>{b}</li>" for b in bullets)

    overview = raw_description[:500] if raw_description else (
        f"This {title} is a high-quality product that delivers exceptional performance and value. "
        f"{'Crafted by ' + brand + ', ' if brand else ''}this item is perfect for anyone seeking reliability and quality."
    )

    return f"""<div style="font-family:Arial,sans-serif;max-width:820px;color:#222;line-height:1.6;margin:0 auto">

  <h2 style="color:#0064d2;border-bottom:3px solid #0064d2;padding-bottom:10px;font-size:20px">
    📦 Product Overview
  </h2>
  <p style="font-size:15px;color:#333">{overview}</p>

  <h2 style="color:#0064d2;border-bottom:3px solid #0064d2;padding-bottom:10px;margin-top:28px;font-size:20px">
    ⭐ Key Features
  </h2>
  <ul style="list-style:none;padding:0;margin:0">{bullet_html}</ul>

  <h2 style="color:#0064d2;border-bottom:3px solid #0064d2;padding-bottom:10px;margin-top:28px;font-size:20px">
    📋 Specifications
  </h2>
  <table style="width:100%;border-collapse:collapse;border:1px solid #dee2e6;border-radius:4px">
    <tbody>{spec_rows}</tbody>
  </table>

  <h2 style="color:#0064d2;border-bottom:3px solid #0064d2;padding-bottom:10px;margin-top:28px;font-size:20px">
    🚚 Shipping & Handling
  </h2>
  <div style="background:#f0f7ff;border:1px solid #b8d9f8;border-radius:6px;padding:16px">
    <p style="margin:4px 0">📦 <strong>Estimated delivery:</strong> {shipping_days} business days</p>
    <p style="margin:4px 0">🕐 <strong>Handling time:</strong> {handling_days} days</p>
    <p style="margin:4px 0">🔒 All items carefully packaged for safe arrival</p>
    <p style="margin:4px 0">✅ Contact us before leaving feedback — we resolve all issues</p>
  </div>

  <div style="background:#fff8e1;border:1px solid #ffe082;border-radius:6px;padding:14px;margin-top:20px">
    <p style="margin:0;font-size:13px;color:#555">
      💬 <strong>Questions?</strong> Message us through eBay — we respond within 24 hours.
    </p>
  </div>

</div>"""


# ── Quality Score ────────────────────────────────────────────────────────────

def calculate_quality_score(
    title: str,
    description: str,
    images: list,
    price: float,
    market_avg,
    specs: dict,
) -> dict:
    """Score from 0–100 across four dimensions."""

    # Title (max 30 pts)
    title_score = 0
    if title:
        words = len(title.split())
        title_score += min(words * 2, 15)
        title_score += 10 if len(title) >= 40 else 5
        title_score += 5 if len(title) <= 80 else 0

    # Description (max 25 pts)
    desc_score = 0
    if description:
        desc_score += min(len(description) // 100, 15)
        for kw in ["feature", "spec", "ship", "quality", "brand", "overview", "✔"]:
            if kw.lower() in description.lower():
                desc_score += 1
        desc_score = min(desc_score, 25)

    # Images (max 25 pts)
    img_score = min(len(images) * 5, 25)

    # Price competitiveness (max 20 pts)
    price_score = 15  # default neutral score
    if market_avg and market_avg > 0 and price:
        diff = abs(price - market_avg) / market_avg
        if diff <= 0.05:
            price_score = 20      # very competitive
        elif diff <= 0.15:
            price_score = 16
        elif diff <= 0.25:
            price_score = 10
        else:
            price_score = max(0, 20 - int(diff * 40))

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
