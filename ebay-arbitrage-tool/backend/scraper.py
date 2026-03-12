"""
Product Scraper — Playwright + BeautifulSoup
Handles dynamic JS-rendered pages as well as static HTML.
"""
import asyncio
import json
import re
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup


# ── Scraped data container ───────────────────────────────────────────────────

class ScrapedProduct:
    def __init__(self):
        self.title: str = ""
        self.brand: str = ""
        self.description: str = ""
        self.price: Optional[float] = None
        self.specs: dict = {}
        self.images: list[str] = []
        self.shipping_days: Optional[int] = None
        self.url: str = ""

    def to_dict(self):
        return {
            "title": self.title,
            "brand": self.brand,
            "description": self.description,
            "price": self.price,
            "specs": self.specs,
            "images": self.images,
            "shipping_days": self.shipping_days,
            "url": self.url,
        }


# ── Helper utilities ─────────────────────────────────────────────────────────

def _extract_price(text: str) -> Optional[float]:
    """Extract the first numeric price from a string."""
    if not text:
        return None
    matches = re.findall(r"[\$£€]?\s*([\d,]+(?:\.\d{1,2})?)", text.replace(",", ""))
    for m in matches:
        try:
            val = float(m)
            if val > 0:
                return val
        except ValueError:
            pass
    return None


def _extract_shipping_days(text: str) -> Optional[int]:
    """Try to extract number of shipping days from a text fragment."""
    if not text:
        return None
    m = re.search(r"(\d+)\s*(?:–|-|to)\s*(\d+)\s*(?:business\s*)?days?", text, re.I)
    if m:
        return int(m.group(2))          # take the upper bound
    m = re.search(r"(\d+)\s*(?:business\s*)?days?", text, re.I)
    if m:
        return int(m.group(1))
    return None


def _abs_url(src: str, base: str) -> str:
    from urllib.parse import urljoin
    return urljoin(base, src)


# ── Generic parser (works on most eCommerce sites) ──────────────────────────

def _parse_html(html: str, url: str) -> ScrapedProduct:
    soup = BeautifulSoup(html, "html.parser")
    product = ScrapedProduct()
    product.url = url
    domain = urlparse(url).netloc

    # ── Title ────────────────────────────────────────────────────────────────
    for sel in [
        'h1[itemprop="name"]', 'h1.product-title', 'h1.product_title',
        'h1.pdp-title', 'h1[class*="title"]', 'h1[class*="product"]',
        'meta[property="og:title"]', 'h1',
    ]:
        tag = soup.select_one(sel)
        if tag:
            product.title = (tag.get("content") or tag.get_text(" ", strip=True))[:300]
            break

    # ── Brand ────────────────────────────────────────────────────────────────
    for sel in [
        '[itemprop="brand"]', '.brand', '.product-brand',
        'meta[property="product:brand"]',
    ]:
        tag = soup.select_one(sel)
        if tag:
            product.brand = (tag.get("content") or tag.get_text(strip=True))[:100]
            break

    # ── Price ────────────────────────────────────────────────────────────────
    for sel in [
        '[itemprop="price"]', '.price', '.product-price',
        '.pdp-price', '[class*="price"]',
        'meta[property="product:price:amount"]',
    ]:
        tag = soup.select_one(sel)
        if tag:
            raw = tag.get("content") or tag.get("data-price") or tag.get_text(strip=True)
            product.price = _extract_price(raw)
            if product.price:
                break

    # ── Description ──────────────────────────────────────────────────────────
    for sel in [
        '[itemprop="description"]', '.product-description',
        '#product-description', '.pdp-description',
        'meta[name="description"]', 'meta[property="og:description"]',
    ]:
        tag = soup.select_one(sel)
        if tag:
            product.description = (tag.get("content") or tag.get_text(" ", strip=True))[:2000]
            break

    # ── Specs ────────────────────────────────────────────────────────────────
    specs = {}
    for table in soup.select("table"):
        for row in table.select("tr"):
            cols = row.select("td, th")
            if len(cols) == 2:
                k = cols[0].get_text(strip=True)
                v = cols[1].get_text(strip=True)
                if k and v:
                    specs[k] = v
    # also pick up dl/dt/dd patterns
    for dl in soup.select("dl"):
        dts = dl.select("dt")
        dds = dl.select("dd")
        for dt, dd in zip(dts, dds):
            k = dt.get_text(strip=True)
            v = dd.get_text(strip=True)
            if k and v:
                specs[k] = v
    product.specs = specs

    # ── Images ───────────────────────────────────────────────────────────────
    seen: set[str] = set()
    for sel in [
        'img[itemprop="image"]', '.product-image img',
        '.pdp-image img', 'img[class*="product"]',
        'img[class*="gallery"]', 'img[src]',
    ]:
        for img in soup.select(sel):
            src = (img.get("data-src") or img.get("data-zoom-image")
                   or img.get("data-original") or img.get("src") or "")
            if src and src not in seen and not src.startswith("data:"):
                abs_src = _abs_url(src, url)
                seen.add(abs_src)
                product.images.append(abs_src)
            if len(product.images) >= 12:
                break
        if len(product.images) >= 12:
            break

    # ── Shipping ─────────────────────────────────────────────────────────────
    for sel in [".shipping", ".delivery", "[class*='ship']", "[class*='deliver']"]:
        tag = soup.select_one(sel)
        if tag:
            days = _extract_shipping_days(tag.get_text())
            if days:
                product.shipping_days = days
                break

    return product


# ── Site-specific parsers ────────────────────────────────────────────────────

def _parse_amazon(soup: BeautifulSoup, url: str) -> ScrapedProduct:
    product = ScrapedProduct()
    product.url = url

    # Title
    tag = soup.select_one("#productTitle")
    if tag:
        product.title = tag.get_text(strip=True)

    # Brand
    tag = soup.select_one("#bylineInfo, #brand")
    if tag:
        product.brand = re.sub(r"(Brand:|Visit the|Store)", "", tag.get_text(strip=True)).strip()

    # Price
    for sel in [".a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice"]:
        tag = soup.select_one(sel)
        if tag:
            product.price = _extract_price(tag.get_text())
            break

    # Description
    tag = soup.select_one("#productDescription, #feature-bullets")
    if tag:
        product.description = tag.get_text(" ", strip=True)[:2000]

    # Specs
    specs = {}
    for row in soup.select("#productDetails_techSpec_section_1 tr, #productDetails_db_sections tr"):
        cols = row.select("td, th")
        if len(cols) == 2:
            specs[cols[0].get_text(strip=True)] = cols[1].get_text(strip=True)
    product.specs = specs

    # Images – Amazon loads them via JS; grab from script tag
    for script in soup.find_all("script", type="text/javascript"):
        text = script.string or ""
        if "ImageBlockATF" in text or "colorImages" in text:
            urls = re.findall(r'"hiRes"\s*:\s*"(https://[^"]+)"', text)
            if not urls:
                urls = re.findall(r'"large"\s*:\s*"(https://[^"]+)"', text)
            product.images = list(dict.fromkeys(urls))[:12]
            break

    return product


# ── Playwright scrape ────────────────────────────────────────────────────────

async def scrape_product(url: str) -> ScrapedProduct:
    """Main entry point — uses Playwright to render page then parses HTML."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError("Playwright not installed. Run: playwright install chromium")

    html = ""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        # Block trackers/ads to speed up scraping
        await page.route(
            "**/{analytics,tracking,ads,beacon}**",
            lambda route: route.abort()
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            # Wait a moment for JS to hydrate
            await asyncio.sleep(2)
            # Scroll to load lazy images
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(1)
            html = await page.content()
        except Exception as e:
            print(f"⚠ Playwright navigation error: {e}")
        finally:
            await browser.close()

    if not html:
        raise ValueError(f"Could not load page: {url}")

    soup = BeautifulSoup(html, "html.parser")
    domain = urlparse(url).netloc.lower()

    # Dispatch to site-specific parsers
    if "amazon" in domain:
        product = _parse_amazon(soup, url)
    else:
        product = _parse_html(html, url)

    # Fallback title from og:title if empty
    if not product.title:
        tag = soup.select_one('meta[property="og:title"]')
        if tag:
            product.title = tag.get("content", "")

    # Fallback images from og:image
    if not product.images:
        for tag in soup.select('meta[property="og:image"]'):
            src = tag.get("content", "")
            if src:
                product.images.append(src)

    return product


# ── Sync wrapper for use from FastAPI endpoints ──────────────────────────────

def scrape_product_sync(url: str) -> ScrapedProduct:
    return asyncio.run(scrape_product(url))
