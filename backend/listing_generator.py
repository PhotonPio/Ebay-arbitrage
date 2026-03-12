"""
backend/listing_generator.py
Uses Anthropic Claude to generate optimized eBay listings.
"""
import json
import logging
from typing import Optional, Dict, List
import anthropic

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


LISTING_PROMPT = """You are an expert eBay seller and marketplace copywriter with 10+ years of experience.
Your task is to transform raw retail product data into an optimized eBay listing.

STRICT RULES:
1. eBay title: MAXIMUM 80 characters. Front-load important keywords. No promotional language.
2. Description: Use proper HTML. Structure with sections. Buyer-focused language.
3. Be factual. Never invent specs not present in the source data.
4. eBay category ID: Pick the most appropriate numeric eBay category ID.

INPUT PRODUCT DATA:
{product_data}

OUTPUT: Return ONLY valid JSON with this exact structure:
{{
  "ebay_title": "...",
  "ebay_description": "...(HTML)...",
  "suggested_category_id": "...",
  "key_features": ["feature1", "feature2", "feature3", "feature4", "feature5"]
}}

The description HTML must follow this structure:
<div class='ebay-listing'>
  <h2>Product Overview</h2>
  <p>[2-3 sentence overview]</p>
  
  <h2>Key Features</h2>
  <ul>
    <li>✔ [Feature 1]</li>
    ...
  </ul>
  
  <h2>Specifications</h2>
  <table>[specs table]</table>
  
  <h2>Shipping Information</h2>
  <p>[shipping details with days provided]</p>
  
  <h2>About the Seller</h2>
  <p>We ship fast and carefully package every item. Customer satisfaction is our priority.</p>
</div>"""


class ListingGenerator:
    def __init__(self):
        self.client = None
        if settings.anthropic_api_key:
            self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def generate(
        self,
        product: Dict,
        shipping_days: int,
        handling_days: int = 2,
    ) -> Dict:
        """Generate an optimized eBay listing from product data."""

        if self.client:
            return await self._generate_with_claude(product, shipping_days, handling_days)
        else:
            logger.warning("No Anthropic API key — using template generator.")
            return self._generate_template(product, shipping_days, handling_days)

    async def _generate_with_claude(self, product: Dict, shipping_days: int, handling_days: int) -> Dict:
        """Use Claude API to generate the listing."""
        product_summary = {
            "title": product.get("title", ""),
            "brand": product.get("brand", ""),
            "description": (product.get("description", "") or "")[:1500],
            "price": product.get("price"),
            "specs": product.get("specs", {}),
            "image_count": len(product.get("images", [])),
            "shipping_days": shipping_days,
            "handling_days": handling_days,
        }

        prompt = LISTING_PROMPT.format(product_data=json.dumps(product_summary, indent=2))

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            content = message.content[0].text
            # Strip markdown code fences if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            result = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error from Claude: {e}")
            return self._generate_template(product, shipping_days, handling_days)
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return self._generate_template(product, shipping_days, handling_days)

    def _generate_template(self, product: Dict, shipping_days: int, handling_days: int) -> Dict:
        """Fallback template-based listing generator (no API needed)."""
        raw_title = product.get("title", "Product")
        brand = product.get("brand", "")
        description = product.get("description", "")
        specs = product.get("specs", {})

        # Build eBay title (max 80 chars)
        title_parts = []
        if brand and brand.lower() not in raw_title.lower():
            title_parts.append(brand)
        title_parts.append(raw_title)
        ebay_title = " ".join(title_parts)
        if len(ebay_title) > 80:
            ebay_title = ebay_title[:77] + "..."

        # Build specs table HTML
        specs_html = ""
        if specs:
            rows = "".join(
                f"<tr><td><strong>{k}</strong></td><td>{v}</td></tr>"
                for k, v in list(specs.items())[:15]
            )
            specs_html = f"<table border='1' cellpadding='6'>{rows}</table>"
        else:
            specs_html = "<p>Please see images for detailed specifications.</p>"

        # Build description
        desc_short = (description[:800] + "...") if len(description) > 800 else description

        ebay_description = f"""<div class='ebay-listing'>
  <h2>Product Overview</h2>
  <p>{desc_short or 'Quality product from a reputable brand.'}</p>

  <h2>Key Features</h2>
  <ul>
    <li>✔ Authentic {brand or 'Brand'} product</li>
    <li>✔ Ships quickly with care</li>
    <li>✔ High-quality item as described</li>
    <li>✔ Satisfaction guaranteed</li>
  </ul>

  <h2>Specifications</h2>
  {specs_html}

  <h2>Shipping Information</h2>
  <p>Estimated delivery: <strong>{shipping_days} business days</strong>.<br>
  Handling time: <strong>{handling_days} business days</strong>.</p>

  <h2>About the Seller</h2>
  <p>We ship fast and carefully package every item. Customer satisfaction is our priority.
  Please message us with any questions before purchasing.</p>
</div>"""

        return {
            "ebay_title": ebay_title,
            "ebay_description": ebay_description,
            "suggested_category_id": "9355",  # default: Everything Else
            "key_features": [
                f"Brand: {brand}" if brand else "Quality product",
                "Ships with care",
                "Satisfaction guaranteed",
                "As described — no surprises",
                "Fast shipping",
            ],
        }
