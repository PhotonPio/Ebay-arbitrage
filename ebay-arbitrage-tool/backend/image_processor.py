"""
Image Processor
Downloads product images, resizes to eBay recommended specs, optimises file size.
"""
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from PIL import Image
import io

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    IMAGE_DIR, PROCESSED_DIR,
    EBAY_IMG_WIDTH, EBAY_IMG_HEIGHT, JPEG_QUALITY,
)

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _ext_from_url(url: str) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def download_and_process_image(url: str, referer: Optional[str] = None) -> Optional[str]:
    """
    Download one image, resize/optimise it, save to PROCESSED_DIR.
    Returns the local file path (relative to project root) or None on failure.
    """
    try:
        headers = dict(BASE_HEADERS)
        if referer:
            headers["Referer"] = referer
        resp = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.content
    except Exception as e:
        print(f"⚠ Image download failed {url}: {e}")
        return None

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        # Resize to fit within eBay recommended canvas (letterbox)
        img.thumbnail((EBAY_IMG_WIDTH, EBAY_IMG_HEIGHT), Image.LANCZOS)

        # Create a white canvas of exact eBay recommended size
        canvas = Image.new("RGB", (EBAY_IMG_WIDTH, EBAY_IMG_HEIGHT), (255, 255, 255))
        offset = (
            (EBAY_IMG_WIDTH - img.width) // 2,
            (EBAY_IMG_HEIGHT - img.height) // 2,
        )
        canvas.paste(img, offset)

        filename = f"{_url_hash(url)}.jpg"
        dest = PROCESSED_DIR / filename
        canvas.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return f"static/processed/{filename}"
    except Exception as e:
        print(f"⚠ Image processing failed {url}: {e}")
        return None


def process_images(urls: list[str], max_images: int = 12, referer: Optional[str] = None) -> list[str]:
    """Process a list of image URLs; return list of local paths."""
    local = []
    for url in urls[:max_images]:
        path = download_and_process_image(url, referer=referer)
        if path:
            local.append(path)
    return local
