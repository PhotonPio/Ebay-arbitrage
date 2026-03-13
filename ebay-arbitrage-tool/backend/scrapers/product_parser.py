import re
from bs4 import BeautifulSoup


def clean_description(raw_html: str) -> str:
    """Convert description HTML into readable plain text with bullet-like formatting."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for bad in soup.select("script,style,noscript"):
        bad.decompose()

    for br in soup.find_all("br"):
        br.replace_with("\n")

    lines: list[str] = []
    for node in soup.select("li,p,div,span,h1,h2,h3,h4,h5,h6"):
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.name == "li":
            lines.append(f"• {text}")
        else:
            lines.append(text)

    if not lines:
        lines = [soup.get_text("\n", strip=True)]

    out = "\n".join([re.sub(r"\s+", " ", line).strip() for line in lines if line.strip()])
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _extract_price(raw: str) -> str:
    if not raw:
        return ""
    m = re.search(r"(?:[$£€]\s*)?([\d,]+(?:\.\d{1,2})?)", raw)
    return m.group(1).replace(",", "") if m else ""


def parse_product_fields(soup: BeautifulSoup) -> dict:
    title = ""
    brand = ""
    description = ""
    price = ""

    for sel in [
        'h1[itemprop="name"]',
        "h1.product-title",
        "h1.product_title",
        "h1",
        'meta[property="og:title"]',
    ]:
        tag = soup.select_one(sel)
        if tag:
            title = (tag.get("content") or tag.get_text(" ", strip=True)).strip()
            if title:
                break

    for sel in ['[itemprop="brand"]', ".brand", 'meta[property="product:brand"]']:
        tag = soup.select_one(sel)
        if tag:
            brand = (tag.get("content") or tag.get_text(" ", strip=True)).strip()
            if brand:
                break

    for sel in [
        '[itemprop="price"]',
        ".price",
        ".product-price",
        'meta[property="product:price:amount"]',
    ]:
        tag = soup.select_one(sel)
        if tag:
            price = _extract_price(tag.get("content") or tag.get("data-price") or tag.get_text(" ", strip=True))
            if price:
                break

    for sel in [
        '[itemprop="description"]',
        ".product-description",
        "#product-description",
        "#feature-bullets",
        'meta[name="description"]',
        'meta[property="og:description"]',
    ]:
        tag = soup.select_one(sel)
        if tag:
            src = tag.get("content") or str(tag)
            description = clean_description(src)
            if description:
                break

    return {
        "title": title[:300],
        "brand": brand[:100],
        "description": description[:4000],
        "price": price,
    }
