"""
backend/image_processor.py
Downloads product images and processes them to eBay specifications.

eBay image requirements:
- Minimum 500px on the longest side (recommended: 1600px)
- JPEG or PNG format
- No borders, watermarks, or text overlays
- Max file size: 12MB per image
"""
import asyncio
import hashlib
import os
import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps
import io

logger = logging.getLogger(__name__)

# eBay recommended image size
EBAY_MIN_SIZE = 500
EBAY_TARGET_SIZE = 1600
EBAY_MAX_FILE_SIZE_MB = 11

STATIC_DIR = Path(__file__).parent.parent / "static" / "processed"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class ImageProcessor:
    """Downloads and optimizes images for eBay listings."""

    async def process_images(self, image_urls: List[str], listing_id: int) -> List[str]:
        """
        Download and process all images for a listing.
        Returns list of local relative paths to processed images.
        """
        if not image_urls:
            return []

        tasks = [self._process_single(url, listing_id, idx)
                 for idx, url in enumerate(image_urls[:12])]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        paths = []
        for r in results:
            if isinstance(r, str):
                paths.append(r)
            else:
                logger.warning(f"Image processing failed: {r}")
        return paths

    async def _process_single(self, url: str, listing_id: int, idx: int) -> Optional[str]:
        """Download one image, process it, save it."""
        try:
            img_bytes = await self._download(url)
            if not img_bytes:
                return None

            img = Image.open(io.BytesIO(img_bytes))
            img = self._optimize(img)

            filename = f"listing_{listing_id}_{idx:02d}.jpg"
            output_path = STATIC_DIR / filename
            img.save(output_path, "JPEG", quality=85, optimize=True)

            # Ensure file size is under eBay limit
            if output_path.stat().st_size > EBAY_MAX_FILE_SIZE_MB * 1024 * 1024:
                img.save(output_path, "JPEG", quality=65, optimize=True)

            return f"/static/processed/{filename}"

        except Exception as e:
            logger.error(f"Failed to process image {url}: {e}")
            return None

    async def _download(self, url: str) -> Optional[bytes]:
        """Download image bytes with error handling."""
        if not url or not url.startswith("http"):
            return None
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": f"https://{urlparse(url).netloc}/",
            }
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if "image" in content_type or len(resp.content) > 1000:
                        return resp.content
        except Exception as e:
            logger.error(f"Download error {url}: {e}")
        return None

    def _optimize(self, img: Image.Image) -> Image.Image:
        """Resize and optimize image to eBay specifications."""
        # Convert to RGB (handle RGBA/P mode images)
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Auto-orient based on EXIF
        img = ImageOps.exif_transpose(img)

        w, h = img.size
        long_side = max(w, h)

        # Upscale if below minimum
        if long_side < EBAY_MIN_SIZE:
            scale = EBAY_MIN_SIZE / long_side
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            w, h = img.size
            long_side = max(w, h)

        # Downscale if above target
        if long_side > EBAY_TARGET_SIZE:
            scale = EBAY_TARGET_SIZE / long_side
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        return img

    def get_image_bytes(self, local_path: str) -> Optional[bytes]:
        """Read processed image as bytes (for eBay API upload)."""
        full_path = Path(__file__).parent.parent / local_path.lstrip("/")
        if full_path.exists():
            return full_path.read_bytes()
        return None
