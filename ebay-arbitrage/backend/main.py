"""
backend/main.py
FastAPI application — all routes for the eBay Arbitrage Tool.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import init_db, get_db, Listing
from backend.models import (
    ScrapeRequest, BulkScrapeRequest, EditListingRequest,
    PublishRequest, ListingResponse, DashboardStats,
)
from backend.scraper import get_scraper
from backend.listing_generator import ListingGenerator
from backend.pricing_engine import PricingEngine
from backend.image_processor import ImageProcessor
from backend.quality_scorer import QualityScorer
from backend.ebay_api import EbayAPI
from config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()

# ── App Init ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="eBay Arbitrage Tool",
    description="Automate eBay listing creation from retail product URLs.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (processed images + frontend)
STATIC_DIR = Path(__file__).parent.parent / "static"
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "processed").mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Services
listing_gen = ListingGenerator()
pricing_engine = PricingEngine()
image_processor = ImageProcessor()
quality_scorer = QualityScorer()
ebay_api = EbayAPI()


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    Path("database").mkdir(exist_ok=True)
    await init_db()
    logger.info("✓ Database initialized")
    logger.info(f"✓ eBay environment: {settings.ebay_environment}")
    logger.info(f"✓ Claude API: {'configured' if settings.anthropic_api_key else 'NOT configured (using template fallback)'}")


# ── Frontend Routes ───────────────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))

@app.get("/preview/{listing_id}")
async def serve_preview(listing_id: int):
    return FileResponse(str(FRONTEND_DIR / "preview.html"))


# ── API: Scrape ───────────────────────────────────────────────────────────────

@app.post("/api/scrape")
async def scrape_product(req: ScrapeRequest, db: AsyncSession = Depends(get_db)):
    """Scrape a product URL and store raw data. Returns listing_id."""
    try:
        scraper = await get_scraper()
        product = await scraper.scrape(req.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape failed: {e}")

    # Calculate price
    raw_price = product.get("price")
    ebay_price = None
    markup = req.markup or settings.default_markup
    if raw_price:
        ebay_price = pricing_engine.calculate_listing_price(raw_price, markup)

    # Calculate shipping
    raw_shipping = product.get("shipping_days")
    ebay_shipping = (raw_shipping * 2) if raw_shipping else 10

    # Save to DB
    listing = Listing(
        source_url=req.url,
        source_site=product.get("source_site"),
        raw_title=product.get("title"),
        raw_brand=product.get("brand"),
        raw_description=product.get("description"),
        raw_price=raw_price,
        raw_specs=product.get("specs", {}),
        raw_images=product.get("images", []),
        raw_shipping_days=raw_shipping,
        markup_percent=markup,
        ebay_price=ebay_price,
        ebay_shipping_days=ebay_shipping,
        handling_days=2,
        status="scraped",
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    return {
        "listing_id": listing.id,
        "product": {
            "title": listing.raw_title,
            "brand": listing.raw_brand,
            "price": listing.raw_price,
            "ebay_price": listing.ebay_price,
            "shipping_days": listing.ebay_shipping_days,
            "image_count": len(product.get("images", [])),
            "has_description": bool(listing.raw_description),
            "has_specs": bool(listing.raw_specs),
        }
    }


# ── API: Generate Listing ─────────────────────────────────────────────────────

@app.post("/api/generate/{listing_id}")
async def generate_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Generate optimized eBay listing from scraped product data."""
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    product = {
        "title": listing.raw_title,
        "brand": listing.raw_brand,
        "description": listing.raw_description,
        "price": listing.raw_price,
        "specs": listing.raw_specs or {},
        "images": listing.raw_images or [],
        "source_url": listing.source_url,
    }

    # 1. Generate listing copy
    generated = await listing_gen.generate(
        product,
        shipping_days=listing.ebay_shipping_days or 10,
        handling_days=listing.handling_days or 2,
    )

    # 2. Process images
    raw_images = listing.raw_images or []
    processed = await image_processor.process_images(raw_images, listing_id)

    # 3. Market price check
    ebay_price = listing.ebay_price or 0
    price_check = await pricing_engine.check_market_price(
        generated.get("ebay_title", listing.raw_title or ""), ebay_price
    )

    # 4. Quality score
    quality = quality_scorer.score(
        title=generated.get("ebay_title", ""),
        description=generated.get("ebay_description", ""),
        image_count=len(processed),
        price_check=price_check,
        brand=listing.raw_brand,
        specs=listing.raw_specs,
    )

    # 5. Profit calculation
    profit = {}
    if listing.raw_price and ebay_price:
        profit = pricing_engine.calculate_profit(listing.raw_price, ebay_price)

    # Update DB
    listing.ebay_title = generated.get("ebay_title", "")[:80]
    listing.ebay_description = generated.get("ebay_description", "")
    listing.ebay_category_id = generated.get("suggested_category_id", "9355")
    listing.processed_images = processed
    listing.market_avg_price = price_check.get("market_avg")
    listing.price_warning = price_check.get("warning", False)
    listing.suggested_price = price_check.get("suggested_price")
    listing.quality_score = quality["total"]
    listing.quality_breakdown = quality["breakdown"]
    listing.profit_amount = profit.get("profit_amount")
    listing.profit_margin = profit.get("profit_margin")
    listing.status = "ready"

    await db.commit()
    await db.refresh(listing)

    return {
        "listing_id": listing.id,
        "ebay_title": listing.ebay_title,
        "ebay_description": listing.ebay_description,
        "ebay_price": listing.ebay_price,
        "ebay_shipping_days": listing.ebay_shipping_days,
        "handling_days": listing.handling_days,
        "processed_images": listing.processed_images,
        "quality_score": listing.quality_score,
        "quality_breakdown": listing.quality_breakdown,
        "price_check": price_check,
        "profit": profit,
        "status": listing.status,
    }


# ── API: Edit Listing ─────────────────────────────────────────────────────────

@app.patch("/api/listing/{listing_id}")
async def edit_listing(listing_id: int, req: EditListingRequest, db: AsyncSession = Depends(get_db)):
    """Update editable fields on a listing."""
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if req.ebay_title is not None:
        listing.ebay_title = req.ebay_title[:80]
    if req.ebay_description is not None:
        listing.ebay_description = req.ebay_description
    if req.ebay_price is not None:
        listing.ebay_price = req.ebay_price
        if listing.raw_price:
            profit = pricing_engine.calculate_profit(listing.raw_price, req.ebay_price)
            listing.profit_amount = profit["profit_amount"]
            listing.profit_margin = profit["profit_margin"]
    if req.ebay_shipping_days is not None:
        listing.ebay_shipping_days = req.ebay_shipping_days
    if req.handling_days is not None:
        listing.handling_days = req.handling_days

    await db.commit()
    return {"success": True, "listing_id": listing_id}


# ── API: Publish Listing ──────────────────────────────────────────────────────

@app.post("/api/publish/{listing_id}")
async def publish_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Upload images and create listing on eBay."""
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.status == "published":
        return {"success": False, "error": "Already published", "listing_id": listing_id}

    # Upload images to eBay Picture Services
    ebay_image_urls = []
    for local_path in (listing.processed_images or [])[:12]:
        hosted_url = await ebay_api.upload_image(local_path)
        if hosted_url:
            ebay_image_urls.append(hosted_url)

    # Create eBay listing
    result = await ebay_api.add_item(
        {
            "ebay_title": listing.ebay_title,
            "ebay_description": listing.ebay_description,
            "ebay_price": listing.ebay_price,
            "ebay_shipping_days": listing.ebay_shipping_days,
            "handling_days": listing.handling_days,
            "ebay_category_id": listing.ebay_category_id or "9355",
        },
        ebay_image_urls,
    )

    if result.get("success"):
        listing.status = "published"
        listing.ebay_listing_id = result.get("item_id")
        listing.ebay_item_url = result.get("item_url")
        await db.commit()
        return {
            "success": True,
            "listing_id": listing_id,
            "ebay_item_id": result.get("item_id"),
            "ebay_url": result.get("item_url"),
        }
    else:
        listing.status = "failed"
        await db.commit()
        return {"success": False, "error": result.get("error"), "listing_id": listing_id}


# ── API: Bulk Scrape ──────────────────────────────────────────────────────────

@app.post("/api/bulk")
async def bulk_scrape(req: BulkScrapeRequest, db: AsyncSession = Depends(get_db)):
    """Process multiple URLs. Returns list of listing IDs."""
    urls = [u.strip() for u in req.urls if u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="No URLs provided")
    if len(urls) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 URLs per batch")

    results = []
    for url in urls:
        try:
            single_req = ScrapeRequest(url=url, markup=req.markup)
            result = await scrape_product(single_req, db)
            results.append({"url": url, "status": "ok", **result})
        except Exception as e:
            results.append({"url": url, "status": "error", "error": str(e)})

    return {"results": results, "total": len(results), "success": sum(1 for r in results if r["status"] == "ok")}


# ── API: Get Listing ──────────────────────────────────────────────────────────

@app.get("/api/listing/{listing_id}")
async def get_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing.__dict__


# ── API: List All Listings ────────────────────────────────────────────────────

@app.get("/api/listings")
async def list_all(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Listing).order_by(desc(Listing.created_at)).limit(100)
    )
    listings = result.scalars().all()
    return [
        {
            "id": l.id,
            "created_at": l.created_at.isoformat() if l.created_at else None,
            "source_url": l.source_url,
            "source_site": l.source_site,
            "raw_title": l.raw_title,
            "raw_price": l.raw_price,
            "ebay_title": l.ebay_title,
            "ebay_price": l.ebay_price,
            "quality_score": l.quality_score,
            "status": l.status,
            "ebay_listing_id": l.ebay_listing_id,
            "ebay_item_url": l.ebay_item_url,
            "profit_amount": l.profit_amount,
            "profit_margin": l.profit_margin,
            "processed_images": l.processed_images,
            "price_warning": l.price_warning,
        }
        for l in listings
    ]


# ── API: Dashboard Stats ──────────────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(Listing))
    published = await db.scalar(
        select(func.count()).select_from(Listing).where(Listing.status == "published")
    )
    drafts = await db.scalar(
        select(func.count()).select_from(Listing).where(Listing.status.in_(["draft", "ready", "scraped"]))
    )
    avg_margin = await db.scalar(
        select(func.avg(Listing.profit_margin)).where(Listing.profit_margin.is_not(None))
    )
    total_profit = await db.scalar(
        select(func.sum(Listing.profit_amount)).where(
            Listing.profit_amount.is_not(None),
            Listing.status == "published"
        )
    )
    top_score = await db.scalar(
        select(func.max(Listing.quality_score)).where(Listing.quality_score.is_not(None))
    )

    recent_result = await db.execute(
        select(Listing).order_by(desc(Listing.created_at)).limit(5)
    )
    recent = recent_result.scalars().all()

    return {
        "total_listings": total or 0,
        "published_listings": published or 0,
        "draft_listings": drafts or 0,
        "avg_profit_margin": round(avg_margin or 0, 1),
        "total_estimated_profit": round(total_profit or 0, 2),
        "top_quality_score": top_score or 0,
        "recent_listings": [
            {
                "id": l.id,
                "raw_title": l.raw_title,
                "ebay_title": l.ebay_title,
                "ebay_price": l.ebay_price,
                "quality_score": l.quality_score,
                "status": l.status,
                "profit_amount": l.profit_amount,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in recent
        ],
    }


# ── API: eBay Credential Check ────────────────────────────────────────────────

@app.get("/api/ebay/verify")
async def verify_ebay():
    result = await ebay_api.verify_credentials()
    return result


# ── API: Delete Listing ───────────────────────────────────────────────────────

@app.delete("/api/listing/{listing_id}")
async def delete_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    listing = await db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(listing)
    await db.commit()
    return {"success": True}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
