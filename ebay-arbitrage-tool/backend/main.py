"""
FlipForge — FastAPI Backend
All API routes, background tasks, and static file serving.
"""
import json
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import (
    DEFAULT_MARKUP, SHIPPING_MULTIPLIER, DEFAULT_HANDLING,
    IMAGE_DIR, PROCESSED_DIR, BASE_DIR, DEMO_MODE,
    EBAY_CLIENT_ID, ANTHROPIC_API_KEY,
)
from backend.database import init_db, get_db, Listing
from backend.scraper import scrape_product_sync
from backend.pricing_engine import calculate_price
from backend.listing_generator import (
    generate_ebay_title, generate_ebay_description, calculate_quality_score,
)
from backend.image_processor import process_images
from backend import ebay_api

# ── Startup ───────────────────────────────────────────────────────────────────
init_db()

# Ensure static dirs exist
(BASE_DIR / "static" / "images").mkdir(parents=True, exist_ok=True)
(BASE_DIR / "static" / "processed").mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="FlipForge — eBay Arbitrage Tool",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static assets and frontend
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

print(f"\n{'='*55}")
print(f"  FlipForge — eBay Arbitrage Tool")
print(f"  Demo Mode: {'✅ ON (no API keys needed)' if DEMO_MODE else '❌ OFF'}")
print(f"  eBay API:  {'✅ Configured' if EBAY_CLIENT_ID else '⚠  Not configured'}")
print(f"  Claude AI: {'✅ Configured' if ANTHROPIC_API_KEY else '⚠  Not configured (using rule-based)'}")
print(f"{'='*55}\n")


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str
    markup: Optional[float] = DEFAULT_MARKUP


class BulkScrapeRequest(BaseModel):
    urls: list[str]
    markup: Optional[float] = DEFAULT_MARKUP


class UpdateListingRequest(BaseModel):
    ebay_title: Optional[str] = None
    ebay_description: Optional[str] = None
    listing_price: Optional[float] = None
    handling_days: Optional[int] = None
    listing_shipping_days: Optional[int] = None


# ── In-memory OAuth token store ───────────────────────────────────────────────
_oauth_tokens: dict = {}


# ── Core listing builder ──────────────────────────────────────────────────────

def _build_listing(db: Session, url: str, markup: float) -> Listing:
    """Scrape URL, generate listing, persist to DB."""

    # 1 — Scrape
    product = scrape_product_sync(url)
    if not product.title:
        product.title = "Product"

    # 2 — Shipping
    retail_days  = product.shipping_days or 5
    listing_days = retail_days * SHIPPING_MULTIPLIER

    # 3 — Pricing
    pricing = {}
    if product.price:
        pricing = calculate_price(product.price, product.title, markup)

    # 4 — Generate listing content
    ebay_title = generate_ebay_title(product.title, product.brand, product.specs)
    ebay_desc  = generate_ebay_description(
        title=ebay_title,
        brand=product.brand,
        raw_description=product.description,
        specs=product.specs,
        shipping_days=listing_days,
        handling_days=DEFAULT_HANDLING,
    )

    # 5 — Images
    local_imgs = process_images(product.images, max_images=8, referer=product.url)

    # 6 — Quality score
    qs = calculate_quality_score(
        title=ebay_title,
        description=ebay_desc,
        images=local_imgs,
        price=pricing.get("listing_price"),
        market_avg=pricing.get("market_avg"),
        specs=product.specs,
    )

    # 7 — Persist
    listing = Listing(
        source_url=url,
        raw_title=product.title,
        raw_brand=product.brand,
        raw_price=product.price,
        raw_description=product.description,
        raw_specs=json.dumps(product.specs),
        raw_images=json.dumps(product.images),
        ebay_title=ebay_title,
        ebay_description=ebay_desc,
        listing_price=pricing.get("listing_price"),
        market_avg_price=pricing.get("market_avg"),
        price_warning=pricing.get("warning", False),
        suggested_price=pricing.get("suggested_price"),
        local_images=json.dumps(local_imgs),
        retail_shipping_days=retail_days,
        listing_shipping_days=listing_days,
        handling_days=DEFAULT_HANDLING,
        quality_score=qs["total"],
        status="draft",
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


# ── UI Routes ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTMLResponse((BASE_DIR / "frontend" / "index.html").read_text())


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    return HTMLResponse((BASE_DIR / "frontend" / "dashboard.html").read_text())


@app.get("/preview/{listing_id}", response_class=HTMLResponse)
async def serve_preview(listing_id: int):
    return HTMLResponse((BASE_DIR / "frontend" / "preview.html").read_text())


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/api/status")
def api_status():
    """Returns current app configuration — useful for the frontend banner."""
    return {
        "demo_mode": DEMO_MODE,
        "ebay_configured": bool(EBAY_CLIENT_ID),
        "claude_configured": bool(ANTHROPIC_API_KEY),
        "ebay_connected": "default" in _oauth_tokens,
        "version": "1.0.0",
    }


@app.post("/api/scrape")
def api_scrape(req: ScrapeRequest, db: Session = Depends(get_db)):
    try:
        listing = _build_listing(db, req.url.strip(), req.markup)
        return {"success": True, "listing": listing.to_dict(), "demo_mode": DEMO_MODE}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scrape/bulk")
def api_bulk_scrape(req: BulkScrapeRequest, db: Session = Depends(get_db)):
    results, errors = [], []
    for url in req.urls[:20]:
        url = url.strip()
        if not url:
            continue
        try:
            listing = _build_listing(db, url, req.markup)
            results.append(listing.to_dict())
        except Exception as e:
            errors.append({"url": url, "error": str(e)})
    return {"success": True, "listings": results, "errors": errors, "demo_mode": DEMO_MODE}


@app.get("/api/listings")
def api_get_listings(
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = db.query(Listing)
    if status:
        q = q.filter(Listing.status == status)
    total = q.count()
    items = q.order_by(Listing.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "listings": [l.to_dict() for l in items]}


@app.get("/api/listings/{listing_id}")
def api_get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing.to_dict()


@app.patch("/api/listings/{listing_id}")
def api_update_listing(
    listing_id: int,
    req: UpdateListingRequest,
    db: Session = Depends(get_db),
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if req.ebay_title is not None:
        listing.ebay_title = req.ebay_title[:80]
    if req.ebay_description is not None:
        listing.ebay_description = req.ebay_description
    if req.listing_price is not None:
        listing.listing_price = req.listing_price
    if req.handling_days is not None:
        listing.handling_days = req.handling_days
    if req.listing_shipping_days is not None:
        listing.listing_shipping_days = req.listing_shipping_days
    listing.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(listing)
    return listing.to_dict()


@app.delete("/api/listings/{listing_id}")
def api_delete_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    db.delete(listing)
    db.commit()
    return {"success": True}


@app.get("/api/stats")
def api_stats(db: Session = Depends(get_db)):
    all_listings = db.query(Listing).all()
    published    = [l for l in all_listings if l.published]
    total_rev    = sum(l.listing_price or 0 for l in published)
    total_cost   = sum(l.raw_price or 0 for l in published)
    profit       = total_rev - total_cost
    margin       = round((profit / total_rev * 100), 1) if total_rev else 0
    recent       = db.query(Listing).order_by(Listing.created_at.desc()).limit(5).all()
    return {
        "total_generated": len(all_listings),
        "total_published": len(published),
        "estimated_profit": round(profit, 2),
        "avg_margin_pct": margin,
        "recent": [l.to_dict() for l in recent],
        "demo_mode": DEMO_MODE,
    }


# ── eBay OAuth ────────────────────────────────────────────────────────────────

@app.get("/api/ebay/auth-url")
def api_ebay_auth_url():
    return {"url": ebay_api.get_auth_url(), "demo_mode": DEMO_MODE}


@app.get("/ebay/callback")
def ebay_callback(code: str, demo: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        tokens = ebay_api.exchange_code_for_token(code)
        _oauth_tokens["default"] = tokens
        return RedirectResponse(url="/?ebay_connected=1")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth failed: {e}")


@app.get("/api/ebay/status")
def api_ebay_status():
    connected = "default" in _oauth_tokens
    token_data = _oauth_tokens.get("default", {})
    return {
        "connected": connected,
        "demo": token_data.get("demo", False),
        "demo_mode": DEMO_MODE,
    }


# ── eBay Publish ──────────────────────────────────────────────────────────────

@app.post("/api/listings/{listing_id}/publish")
def api_publish_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    tokens = _oauth_tokens.get("default")
    if not tokens and not DEMO_MODE:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated with eBay. Connect your account first.",
        )

    # Use demo token if in demo mode
    access_token = (tokens or {}).get("access_token", "DEMO_ACCESS_TOKEN")

    # Upload images
    ebay_image_urls = []
    for local_path in listing.local_images_list()[:12]:
        full_path = BASE_DIR / local_path
        img_url = ebay_api.upload_image(access_token, str(full_path))
        if img_url:
            ebay_image_urls.append(img_url)

    # Create inventory item
    inv_result = ebay_api.create_inventory_item(access_token, listing.to_dict(), ebay_image_urls)
    if inv_result["status"] not in (200, 201, 204):
        raise HTTPException(status_code=500, detail=f"Inventory creation failed: {inv_result['body']}")

    sku = inv_result["sku"]

    # Create offer
    offer_result = ebay_api.create_offer(access_token, listing.to_dict(), sku)
    if offer_result["status"] not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Offer creation failed: {offer_result['body']}")

    offer_id = offer_result["offer_id"]

    # Publish offer
    publish_result = ebay_api.publish_offer(access_token, offer_id)

    listing.published = True
    listing.published_at = datetime.utcnow()
    listing.status = "published"
    listing.ebay_listing_id = publish_result.get("listing_id")
    listing.ebay_draft_id = offer_id
    db.commit()
    db.refresh(listing)

    return {
        "success": True,
        "listing": listing.to_dict(),
        "ebay_id": listing.ebay_listing_id,
        "demo": DEMO_MODE,
        "message": "Listing simulated (demo mode)" if DEMO_MODE else "Listing published to eBay",
    }
