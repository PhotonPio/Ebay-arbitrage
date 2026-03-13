import asyncio
import random
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup

from config.settings import HTTP_TIMEOUT


@dataclass
class ScrapeErrorInfo:
    url: str
    error_type: str
    message: str
    retry_suggested: bool


class ScrapedProduct:
    def __init__(self):
        self.title = ""
        self.price: float = 0.0
        self.price_unavailable: bool = False
        self.brand = ""
        self.description = ""
        self.images: list[str] = []
        self.variants: list[dict] = []
        self.source_url = ""
        self.specs: dict = {}
        self.shipping_days: Optional[int] = None
        self.error: Optional[ScrapeErrorInfo] = None

    def to_dict(self):
        d = self.__dict__.copy()
        if self.error:
            d["error"] = self.error.__dict__
        return d


UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
]


def _extract_price(text: str) -> Optional[float]:
    if not text:
        return None
    m = re.search(r"(?:[$£€]\s*)?([\d,]+(?:\.\d{1,2})?)", text)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _extract_shipping_days(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d+)\s*(?:-|to|–)\s*(\d+)\s*(?:business\s*)?days?", text, re.I)
    if m:
        return int(m.group(2))
    m = re.search(r"(\d+)\s*(?:business\s*)?days?", text, re.I)
    return int(m.group(1)) if m else None


def _clean_description(node) -> str:
    if node is None:
        return ""
    soup = BeautifulSoup(str(node), "html.parser")
    for bad in soup.select("script,style,noscript"):
        bad.decompose()
    for br in soup.select("br"):
        br.replace_with("\n")
    lines = []
    for li in soup.select("li"):
        t = li.get_text(" ", strip=True)
        if t:
            lines.append(f"• {t}")
    txt = soup.get_text("\n", strip=True)
    if txt:
        lines.extend([x.strip() for x in txt.splitlines() if x.strip() and not x.strip().startswith("•")])
    return "\n".join(dict.fromkeys(lines))[:4000]


def _extract_images(soup: BeautifulSoup, base: str) -> list[str]:
    out, seen = [], set()
    for img in soup.select("img,source"):
        for a in ["src", "data-src", "data-original", "data-zoom-image", "srcset", "data-srcset"]:
            raw = img.get(a)
            if not raw:
                continue
            for bit in raw.split(","):
                u = bit.strip().split(" ")[0]
                if not u or u.startswith("data:"):
                    continue
                absu = urljoin(base, u)
                if re.search(r"\.(jpg|jpeg|png|webp)(\?|$)", absu, re.I) and absu not in seen:
                    seen.add(absu)
                    out.append(absu)
    for m in re.findall(r"https?://[^\"'\s>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\"'\s>]*)?", str(soup), re.I):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def _extract_variants(soup: BeautifulSoup) -> list[dict]:
    groups = {}
    for sel in soup.select("select"):
        name = sel.get("name") or sel.get("id") or "Option"
        opts = [o.get_text(" ", strip=True) for o in sel.select("option") if o.get_text(" ", strip=True).lower() not in {"select", "choose"}]
        if len(set(opts)) > 1:
            groups[name] = sorted(set(opts))
    for el in soup.select("[data-color],[data-size]"):
        if el.get("data-color"):
            groups.setdefault("Color", set()).add(el.get("data-color"))
        if el.get("data-size"):
            groups.setdefault("Size", set()).add(el.get("data-size"))
    out = []
    for k, v in groups.items():
        vals = sorted(v) if isinstance(v, set) else v
        if len(vals) > 1:
            out.append({"name": k, "options": vals})
    return out


def _parse_generic(soup: BeautifulSoup, url: str) -> ScrapedProduct:
    p = ScrapedProduct()
    p.source_url = url
    title_tag = soup.select_one('h1[itemprop="name"],h1.product-title,meta[property="og:title"],h1,title')
    p.title = (title_tag.get("content") if title_tag and title_tag.get("content") else title_tag.get_text(" ", strip=True) if title_tag else "").strip()
    if not p.title:
        raise ValueError("Could not extract title from page")
    p.brand = (soup.select_one('[itemprop="brand"],meta[property="product:brand"],.brand') or {}).get_text(" ", strip=True) if soup.select_one('[itemprop="brand"],meta[property="product:brand"],.brand') else ""
    desc_tag = soup.select_one('[itemprop="description"],.product-description,#product-description,meta[name="description"]')
    p.description = _clean_description(desc_tag.get("content") if desc_tag and desc_tag.get("content") else desc_tag)
    price_tag = soup.select_one('[itemprop="price"],.price,meta[property="product:price:amount"]')
    p.price = _extract_price((price_tag.get("content") if price_tag and price_tag.get("content") else price_tag.get_text(" ", strip=True) if price_tag else soup.get_text(" ", strip=True))) or 0.0
    p.price_unavailable = p.price == 0.0
    p.images = _extract_images(soup, url)
    p.variants = _extract_variants(soup)
    return p


def _parse_amazon(soup, url): return _parse_generic(soup, url)
def _parse_bestbuy(soup, url): return _parse_generic(soup, url)
def _parse_target(soup, url): return _parse_generic(soup, url)
def _parse_walmart(soup, url): return _parse_generic(soup, url)


async def _fetch_with_playwright(url: str) -> str:
    from playwright.async_api import async_playwright
    headers = {
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
    }
    ua = random.choice(UA_POOL)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(user_agent=ua, extra_http_headers=headers)
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
        await page.mouse.move(120, 240)
        for wait in ["networkidle", "domcontentloaded", "load"]:
            try:
                await page.goto(url, wait_until=wait, timeout=30000)
                await page.wait_for_timeout(600)
                title = await page.title()
                if title.strip():
                    break
            except Exception:
                continue
        await page.mouse.wheel(0, 500)
        await page.wait_for_timeout(300)
        await page.mouse.wheel(0, 1400)
        await page.wait_for_timeout(300)
        html = await page.content()
        await browser.close()
    return html


async def scrape_product(url: str, download_images: bool = False) -> ScrapedProduct:
    p = ScrapedProduct()
    p.source_url = url
    try:
        try:
            html = await _fetch_with_playwright(url)
        except Exception:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
                html = (await client.get(url)).text
        lowered = html.lower()
        if any(k in lowered for k in ["access denied", "robot", "captcha", "cloudflare", "403 forbidden"]):
            p.error = ScrapeErrorInfo(url, "bot_blocked", "Bot protection detected", False)
            return p

        soup = BeautifulSoup(html, "html.parser")
        domain = urlparse(url).netloc.lower()
        if "amazon." in domain:
            return _parse_amazon(soup, url)
        if "bestbuy." in domain:
            return _parse_bestbuy(soup, url)
        if "target." in domain:
            return _parse_target(soup, url)
        if "walmart." in domain:
            return _parse_walmart(soup, url)
        return _parse_generic(soup, url)
    except httpx.TimeoutException:
        p.error = ScrapeErrorInfo(url, "timeout", "Timed out while loading page", True)
        return p
    except httpx.HTTPError as e:
        p.error = ScrapeErrorInfo(url, "network_error", str(e), True)
        return p
    except Exception as e:
        p.error = ScrapeErrorInfo(url, "parse_failed", str(e), True)
        return p


def scrape_product_sync(url: str, download_images: bool = False) -> ScrapedProduct:
    return asyncio.run(scrape_product(url, download_images=download_images))
