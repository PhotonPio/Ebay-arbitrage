import hashlib
import io
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image

from config.settings import EBAY_IMG_HEIGHT, EBAY_IMG_WIDTH, HTTP_TIMEOUT, JPEG_QUALITY, PROCESSED_DIR

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _dedup_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _alt_url(url: str) -> str:
    return url.replace("_AC_SX300", "_AC_SL1500")


def download_and_process_image(url: str, referer: str | None = None) -> str | None:
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    raw = None
    for candidate in [url, _alt_url(url)]:
        try:
            r = httpx.get(candidate, timeout=HTTP_TIMEOUT, follow_redirects=True, headers=headers)
            r.raise_for_status()
            raw = r.content
            break
        except Exception:
            continue
    if raw is None:
        return None

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        img.thumbnail((EBAY_IMG_WIDTH, EBAY_IMG_HEIGHT), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (EBAY_IMG_WIDTH, EBAY_IMG_HEIGHT), "white")
        canvas.paste(img, ((EBAY_IMG_WIDTH - img.width) // 2, (EBAY_IMG_HEIGHT - img.height) // 2))

        filename = f"{_dedup_key(url)[:14]}.jpg"
        dest = PROCESSED_DIR / filename
        quality = JPEG_QUALITY
        while True:
            canvas.save(dest, "JPEG", quality=quality, optimize=True, progressive=True)
            if dest.stat().st_size <= 2 * 1024 * 1024 or quality <= 50:
                break
            quality -= 5
        return f"static/processed/{filename}"
    except Exception:
        return None


def process_images(urls: list[str], max_images: int = 12, referer: str | None = None) -> list[str]:
    seen = set()
    out = []
    for u in urls:
        k = _dedup_key(u)
        if k in seen:
            continue
        seen.add(k)
        path = download_and_process_image(u, referer=referer)
        if path:
            out.append(path)
        if len(out) >= max_images:
            break
    return out
