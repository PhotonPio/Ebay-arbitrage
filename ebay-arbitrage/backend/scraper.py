"""
backend/scraper.py
Playwright-powered product scraper.
Handles dynamic JS-rendered pages and common retail site structures.
"""
import asyncio
import re
import json
from typing import Optional, Dict, List
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Page, Browser
import logging

logger = logging.getLogger(__name__)


class ProductScraper:
    """Universal product scraper using Playwright."""

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._playwright = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def scrape(self, url: str) -> Dict:
        """Scrape product data from any retail URL."""
        if not self._browser:
            await self.start()

        domain = urlparse(url).netloc.lower()
        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Try structured data first (JSON-LD)
            product = await self._extract_json_ld(page)

            # Supplement with DOM extraction
            dom_data = await self._extract_dom(page, domain)

            # Merge: JSON-LD wins if it has data, DOM fills gaps
            merged = self._merge(product, dom_data, url, domain)
            return merged

        except Exception as e:
            logger.error(f"Scrape error for {url}: {e}")
            # Return partial data with error note
            return {
                "title": f"[Scrape failed: {str(e)[:80]}]",
                "brand": None,
                "description": None,
                "price": None,
                "specs": {},
                "images": [],
                "shipping_days": None,
                "source_url": url,
                "source_site": domain,
                "error": str(e),
            }
        finally:
            await context.close()

    async def _extract_json_ld(self, page: Page) -> Dict:
        """Extract product data from JSON-LD structured data."""
        scripts = await page.query_selector_all('script[type="application/ld+json"]')
        for script in scripts:
            try:
                content = await script.inner_text()
                data = json.loads(content)
                # Handle @graph arrays
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") in ("Product", "IndividualProduct"):
                            return self._parse_json_ld_product(item)
                elif isinstance(data, dict):
                    if data.get("@type") in ("Product", "IndividualProduct"):
                        return self._parse_json_ld_product(data)
                    # Check @graph
                    for item in data.get("@graph", []):
                        if item.get("@type") in ("Product", "IndividualProduct"):
                            return self._parse_json_ld_product(item)
            except Exception:
                continue
        return {}

    def _parse_json_ld_product(self, data: Dict) -> Dict:
        """Parse a Product JSON-LD object."""
        offers = data.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        price = None
        try:
            price = float(offers.get("price", 0) or 0) or None
        except (ValueError, TypeError):
            pass

        images = data.get("image", [])
        if isinstance(images, str):
            images = [images]
        elif isinstance(images, dict):
            images = [images.get("url", "")]

        brand = data.get("brand", {})
        if isinstance(brand, dict):
            brand = brand.get("name")

        specs = {}
        for prop in data.get("additionalProperty", []):
            if isinstance(prop, dict):
                specs[prop.get("name", "")] = str(prop.get("value", ""))

        return {
            "title": data.get("name"),
            "brand": brand,
            "description": self._clean_html(data.get("description", "")),
            "price": price,
            "specs": specs,
            "images": [img for img in images if img],
            "shipping_days": None,
        }

    async def _extract_dom(self, page: Page, domain: str) -> Dict:
        """Fallback DOM extraction with site-specific selectors."""
        result = {
            "title": None,
            "brand": None,
            "description": None,
            "price": None,
            "specs": {},
            "images": [],
            "shipping_days": None,
        }

        # ── Title ──────────────────────────────────────────────
        title_selectors = [
            "h1[itemprop='name']", "h1.product-title", "h1.product-name",
            "h1.pdp-title", "[data-testid='product-title']",
            ".product__title h1", "#productTitle", "h1"
        ]
        for sel in title_selectors:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text and len(text) > 3:
                    result["title"] = text[:500]
                    break

        # ── Price ──────────────────────────────────────────────
        price_selectors = [
            "[itemprop='price']", ".price-now", ".current-price",
            "[data-testid='price']", ".pdp-price", "#priceblock_ourprice",
            ".a-price-whole", ".product-price", ".price", ".Price"
        ]
        for sel in price_selectors:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                price = self._parse_price(text)
                if price:
                    result["price"] = price
                    break

        # ── Images ─────────────────────────────────────────────
        img_selectors = [
            ".product-image img", ".pdp-image img", "[data-testid='product-image'] img",
            ".gallery img", "#imageBlock img", ".product__media img",
            "[itemprop='image']", ".swiper-slide img"
        ]
        seen = set()
        for sel in img_selectors:
            els = await page.query_selector_all(sel)
            for el in els[:10]:
                src = await el.get_attribute("src") or await el.get_attribute("data-src") or ""
                src = src.strip()
                if src and src not in seen and not src.startswith("data:"):
                    seen.add(src)
                    result["images"].append(src)

        # ── Description ────────────────────────────────────────
        desc_selectors = [
            "[itemprop='description']", ".product-description",
            "#feature-bullets", ".pdp-description", ".product__description",
            "[data-testid='product-description']"
        ]
        for sel in desc_selectors:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if len(text) > 20:
                    result["description"] = text[:3000]
                    break

        # ── Brand ──────────────────────────────────────────────
        brand_selectors = [
            "[itemprop='brand']", ".product-brand", ".brand-name",
            "[data-testid='brand']", ".pdp-brand"
        ]
        for sel in brand_selectors:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    result["brand"] = text[:100]
                    break

        # ── Specs Table ────────────────────────────────────────
        spec_rows = await page.query_selector_all(
            "table.product-specs tr, .specifications tr, "
            "[data-testid='specs'] li, .spec-list li"
        )
        for row in spec_rows[:20]:
            cells = await row.query_selector_all("td, th, dt, dd")
            if len(cells) >= 2:
                key = (await cells[0].inner_text()).strip().rstrip(":")
                val = (await cells[1].inner_text()).strip()
                if key and val:
                    result["specs"][key] = val

        # ── Shipping Estimate ──────────────────────────────────
        ship_selectors = [
            ".delivery-estimate", ".shipping-estimate",
            "[data-testid='delivery']", ".delivery-message"
        ]
        for sel in ship_selectors:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                days = self._extract_shipping_days(text)
                if days:
                    result["shipping_days"] = days
                    break

        return result

    def _merge(self, json_ld: Dict, dom: Dict, url: str, domain: str) -> Dict:
        """Merge JSON-LD and DOM data, preferring JSON-LD."""
        merged = {}
        for key in ("title", "brand", "description", "price", "shipping_days"):
            merged[key] = json_ld.get(key) or dom.get(key)

        # Specs: merge both
        merged["specs"] = {**dom.get("specs", {}), **json_ld.get("specs", {})}

        # Images: JSON-LD first, then DOM, deduplicate
        images = json_ld.get("images", []) + dom.get("images", [])
        seen = set()
        unique = []
        for img in images:
            if img and img not in seen:
                seen.add(img)
                unique.append(img)
        merged["images"] = unique[:12]  # max 12 images

        merged["source_url"] = url
        merged["source_site"] = domain

        return merged

    def _parse_price(self, text: str) -> Optional[float]:
        """Extract a float price from a string like '$1,299.99'."""
        text = re.sub(r"[^\d.,]", "", text.replace(",", ""))
        matches = re.findall(r"\d+\.?\d*", text)
        for m in matches:
            try:
                val = float(m)
                if val > 0.5:
                    return round(val, 2)
            except ValueError:
                pass
        return None

    def _extract_shipping_days(self, text: str) -> Optional[int]:
        """Extract number of days from shipping text."""
        match = re.search(r"(\d+)\s*(?:business\s+)?days?", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"(\d+)\s*-\s*(\d+)\s*(?:business\s+)?days?", text, re.IGNORECASE)
        if match:
            return int(match.group(2))
        return None

    def _clean_html(self, text: str) -> str:
        """Strip HTML tags from text."""
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()[:3000]


# Singleton instance
_scraper_instance: Optional[ProductScraper] = None


async def get_scraper() -> ProductScraper:
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = ProductScraper()
        await _scraper_instance.start()
    return _scraper_instance
