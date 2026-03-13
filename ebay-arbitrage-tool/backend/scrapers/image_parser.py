import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

IMAGE_EXT_RE = re.compile(r"\.(?:jpg|jpeg|png|webp|gif)(?:$|\?)", re.I)
HTTP_IMAGE_RE = re.compile(r"https?://[^\"'\s>]+\.(?:jpg|jpeg|png|webp|gif)(?:\?[^\"'\s>]*)?", re.I)


def _parse_srcset(srcset: str) -> list[str]:
    if not srcset:
        return []
    out: list[str] = []
    for part in srcset.split(","):
        url = part.strip().split(" ")[0]
        if url:
            out.append(url)
    return out


def _add_url(urls: list[str], seen: set[str], src: str, base_url: str):
    if not src or src.startswith("data:"):
        return
    absolute = urljoin(base_url, src.strip())
    if not absolute.startswith("http"):
        return
    if not IMAGE_EXT_RE.search(absolute):
        return
    if absolute not in seen:
        seen.add(absolute)
        urls.append(absolute)


def _extract_json_images(soup: BeautifulSoup, base_url: str, urls: list[str], seen: set[str]):
    for script in soup.find_all("script"):
        raw = script.string or script.get_text() or ""
        if not raw or "image" not in raw.lower():
            continue

        for found in HTTP_IMAGE_RE.findall(raw):
            _add_url(urls, seen, found, base_url)

        if "application/ld+json" not in (script.get("type") or ""):
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        stack = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                img = node.get("image")
                if isinstance(img, str):
                    _add_url(urls, seen, img, base_url)
                elif isinstance(img, list):
                    for item in img:
                        if isinstance(item, str):
                            _add_url(urls, seen, item, base_url)
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)


def extract_image_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Extract all direct image URLs from tags, lazy attributes, and embedded JSON/script content."""
    urls: list[str] = []
    seen: set[str] = set()

    for img in soup.select("img,source"):
        candidates = [
            img.get("src"),
            img.get("data-src"),
            img.get("data-srcset"),
            img.get("data-lazy"),
            img.get("data-original"),
            img.get("data-zoom-image"),
            img.get("srcset"),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            for option in _parse_srcset(candidate):
                _add_url(urls, seen, option, base_url)
            _add_url(urls, seen, candidate, base_url)

    for meta in soup.select(
        'meta[property="og:image"],meta[property="og:image:secure_url"],meta[name="twitter:image"],meta[name="twitter:image:src"]'
    ):
        _add_url(urls, seen, meta.get("content", ""), base_url)

    _extract_json_images(soup, base_url, urls, seen)
    return urls
