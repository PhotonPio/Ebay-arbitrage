"""
Product Scraper — Playwright + BeautifulSoup
Handles dynamic JS-rendered pages as well as static HTML.
"""
import asyncio
import json
import re
from typing import Optional
from urllib.parse import urlparse

import httpx
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

def _parse_srcset(srcset: str) -> list[str]:
    if not srcset:
        return []
    urls = []
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        url = part.split()[0]
        if url:
            urls.append(url)
    return urls

def _collect_meta_images(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    for sel in [
        'meta[property="og:image"]',
        'meta[name="og:image"]',
        'meta[property="twitter:image"]',
        'meta[name="twitter:image"]',
    ]:
        for tag in soup.select(sel):
            src = tag.get("content", "")
            if src:
                urls.append(src)
    for tag in soup.select('link[rel="preload"][as="image"]'):
        src = tag.get("href", "")
        if src:
            urls.append(src)
    return urls

def _title_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path:
        return "Product"
    slug = path.split("/")[-1]
    slug = re.sub(r"\.html?$", "", slug, flags=re.I)
    slug = re.sub(r"[-_]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    return slug[:120] or "Product"

def _brand_from_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    host = host.split(":")[0]
    parts = [p for p in host.split(".") if p and p not in {"www", "com", "net", "org", "co"}]
    if not parts:
        return ""
    return parts[-1].capitalize()

def _looks_blocked(html: str) -> bool:
    if not html:
        return True
    lowered = html.lower()
    markers = [
        "access denied",
        "request blocked",
        "unusual traffic",
        "bot detection",
        "captcha",
        "please verify",
        "security check",
    ]
    return any(m in lowered for m in markers)

def _parse_json_ld(soup: BeautifulSoup, url: str) -> Optional[ScrapedProduct]:
    """Extract product data from JSON-LD blocks if present."""
    blocks = soup.find_all("script", type="application/ld+json")
    if not blocks:
        return None

    def _iter_items(obj):
        if isinstance(obj, list):
            for item in obj:
                yield from _iter_items(item)
        elif isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from _iter_items(v)

    product_node = None
    for block in blocks:
        try:
            data = json.loads(block.string or block.get_text() or "{}")
        except Exception:
            continue
        for item in _iter_items(data):
            if isinstance(item, dict) and str(item.get("@type", "")).lower() == "product":
                product_node = item
                break
        if product_node:
            break

    if not product_node:
        return None

    product = ScrapedProduct()
    product.url = url

    title = product_node.get("name") or ""
    if title:
        product.title = str(title)[:300]

    brand = product_node.get("brand")
    if isinstance(brand, dict):
        product.brand = str(brand.get("name", ""))[:100]
    elif isinstance(brand, str):
        product.brand = brand[:100]

    description = product_node.get("description") or ""
    if description:
        product.description = str(description)[:2000]

    image = product_node.get("image") or []
    if isinstance(image, str):
        product.images = [image]
    elif isinstance(image, list):
        product.images = [str(i) for i in image if i][:12]

    offers = product_node.get("offers")
    if isinstance(offers, dict):
        raw_price = offers.get("price") or offers.get("priceSpecification", {}).get("price")
        product.price = _extract_price(str(raw_price)) if raw_price is not None else None
    elif isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict) and offer.get("price"):
                product.price = _extract_price(str(offer.get("price")))
                if product.price:
                    break

    return product


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
        'img[class*="gallery"]', 'img[src]', 'source[srcset]'
    ]:
        for img in soup.select(sel):
            candidates = []
            candidates += _parse_srcset(img.get("data-srcset", ""))
            candidates += _parse_srcset(img.get("srcset", ""))
            candidates += [
                img.get("data-src"),
                img.get("data-zoom-image"),
                img.get("data-original"),
                img.get("data-lazy"),
                img.get("data-image"),
                img.get("src"),
            ]
            for src in [c for c in candidates if c]:
                if src.startswith("data:"):
                    continue
                abs_src = _abs_url(src, url)
                if abs_src not in seen:
                    seen.add(abs_src)
                    product.images.append(abs_src)
                if len(product.images) >= 12:
                    break
            if len(product.images) >= 12:
                break
        if len(product.images) >= 12:
            break

    if not product.images:
        for src in _collect_meta_images(soup):
            abs_src = _abs_url(src, url)
            if abs_src not in seen:
                seen.add(abs_src)
                product.images.append(abs_src)
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

    async def _fetch_html(target_url: str, user_agent: str, extra_headers: dict[str, str]) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                timezone_id="America/Los_Angeles",
                extra_http_headers=extra_headers,
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
            )
            page = await context.new_page()

            # Block trackers/ads to speed up scraping
            await page.route(
                "**/{analytics,tracking,ads,beacon}**",
                lambda route: route.abort()
            )

            try:
                for wait_until in ("domcontentloaded", "load", "networkidle"):
                    try:
                        await page.goto(target_url, wait_until=wait_until, timeout=45_000)
                        break
                    except Exception:
                        pass
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(1)
                return await page.content()
            finally:
                await browser.close()

    async def _fetch_html_httpx(target_url: str, extra_headers: dict[str, str]) -> str:
        headers = {
            "User-Agent": extra_headers.get("user-agent", ""),
            "Accept": extra_headers.get("accept", "*/*"),
            "Accept-Language": extra_headers.get("accept-language", "en-US,en;q=0.9"),
            "Referer": extra_headers.get("referer", ""),
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            resp = await client.get(target_url, headers=headers)
            if resp.status_code >= 400:
                return ""
            return resp.text or ""

    html = ""
    ua_windows = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    ua_mac = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    headers = {
        "accept-language": "en-US,en;q=0.9",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "upgrade-insecure-requests": "1",
        "user-agent": ua_windows,
    }

    try:
        html = await _fetch_html(url, ua_windows, headers)
        if _looks_blocked(html):
            headers["user-agent"] = ua_mac
            html = await _fetch_html(url, ua_mac, headers)
        if _looks_blocked(html):
            # Fallback to a simple HTTP fetch (some sites block Playwright but allow HTML)
            html = await _fetch_html_httpx(url, headers)
    except Exception as e:
        print(f"⚠ Playwright navigation error: {e}")

    if not html:
        # Return a minimal product so the app can continue gracefully.
        product = ScrapedProduct()
        product.url = url
        product.title = _title_from_url(url)
        product.brand = _brand_from_domain(url)
        product.specs = {"Scrape Error": "Could not load page"}
        return product

    soup = BeautifulSoup(html, "html.parser")
    domain = urlparse(url).netloc.lower()

    # Try structured data first (most reliable for modern sites)
    product = _parse_json_ld(soup, url) or ScrapedProduct()
    product.url = url

    # Dispatch to site-specific parsers
    if "amazon" in domain:
        parsed = _parse_amazon(soup, url)
    else:
        parsed = _parse_html(html, url)

    # Merge parsed fields where JSON-LD is missing
    if not product.title:
        product.title = parsed.title
    if not product.brand:
        product.brand = parsed.brand
    if not product.description:
        product.description = parsed.description
    if not product.price:
        product.price = parsed.price
    if not product.specs:
        product.specs = parsed.specs
    if not product.images:
        product.images = parsed.images
    if not product.shipping_days:
        product.shipping_days = parsed.shipping_days

    # Fallback title from og:title if empty
    if not product.title:
        tag = soup.select_one('meta[property="og:title"]')
        if tag:
            product.title = tag.get("content", "")

    # Fallback images from og:image
    if not product.images:
        for src in _collect_meta_images(soup):
            product.images.append(src)

    if _looks_blocked(html) and not (product.title or product.price or product.images):
        product.specs = product.specs or {}
        product.specs["Scrape Error"] = "Access denied by site"
        if not product.title:
            product.title = _title_from_url(url)
        if not product.brand:
            product.brand = _brand_from_domain(url)

    return product


# ── Sync wrapper for use from FastAPI endpoints ──────────────────────────────

def scrape_product_sync(url: str) -> ScrapedProduct:
    return asyncio.run(scrape_product(url))
