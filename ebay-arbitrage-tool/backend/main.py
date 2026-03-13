import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend import ebay_api
from backend.database import Listing, ScannerResult, get_db, init_db
from backend.exceptions import FlipForgeError
from backend.export import export_amazon, export_bulk_zip, export_etsy, export_facebook, export_generic_csv
from backend.image_processor import process_images
from backend.listing_generator import calculate_quality_score, generate_ebay_description, generate_ebay_title
from backend.pricing_engine import calculate_price
from backend.scanner import scan_all_targets
from backend.scraper import scrape_product_sync
from backend.vero_checker import check_brand
from config.settings import BASE_DIR, DEFAULT_HANDLING, DEFAULT_MARKUP, DEMO_MODE, SHIPPING_MULTIPLIER

init_db()
(BASE_DIR / "static" / "processed").mkdir(parents=True, exist_ok=True)
app = FastAPI(title="FlipForge", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.exception_handler(FlipForgeError)
async def flipforge_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"success": False, "error_type": type(exc).__name__, "message": str(exc)})


class ScrapeRequest(BaseModel):
    url: str
    markup: float = DEFAULT_MARKUP
    download_images: bool = False


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((BASE_DIR / "frontend" / "index.html").read_text())


@app.get("/preview/{listing_id}", response_class=HTMLResponse)
async def preview_page(listing_id: int):
    return HTMLResponse((BASE_DIR / "frontend" / "preview.html").read_text())


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return HTMLResponse((BASE_DIR / "frontend" / "dashboard.html").read_text())


@app.get("/scanner", response_class=HTMLResponse)
async def scanner_page():
    return HTMLResponse((BASE_DIR / "frontend" / "scanner.html").read_text())


@app.get("/api/status")
def status():
    return {"demo_mode": DEMO_MODE, "ebay_configured": True, "claude_configured": True, "ebay_connected": DEMO_MODE, "version": "2.0"}


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    listings = db.query(Listing).all()
    return {
        "total_generated": len(listings),
        "published": sum(1 for l in listings if l.published),
        "net_profit": round(sum((l.net_profit or 0) for l in listings), 2),
        "avg_quality": round(sum((l.quality_score or 0) for l in listings) / len(listings), 2) if listings else 0,
    }


@app.get("/api/listings")
def get_listings(db: Session = Depends(get_db)):
    return {"success": True, "listings": [l.to_dict() for l in db.query(Listing).order_by(Listing.id.desc()).all()]}


@app.post("/api/scrape")
def scrape(req: ScrapeRequest, db: Session = Depends(get_db)):
    try:
        product = scrape_product_sync(req.url, download_images=req.download_images)
        if product.error:
            return JSONResponse(status_code=500, content={"success": False, "error_type": product.error.error_type, "message": product.error.message})

        pricing = calculate_price(product.price or 0, product.title, req.markup)
        title = generate_ebay_title(product.title, product.brand, product.specs)
        description = generate_ebay_description(title, product.brand, product.description, product.specs, (product.shipping_days or 5) * SHIPPING_MULTIPLIER, DEFAULT_HANDLING)
        processed = process_images(product.images, max_images=12, referer=product.source_url)
        quality = calculate_quality_score(title, description, processed, pricing["listing_price"], pricing.get("market_avg"), product.specs)
        vero = check_brand(product.brand)

        listing = Listing(
            source_url=product.source_url,
            raw_title=product.title,
            raw_brand=product.brand,
            raw_price=product.price,
            raw_description=product.description,
            raw_specs=json.dumps(product.specs),
            raw_images=json.dumps(product.images),
            ebay_title=title,
            ebay_description=description,
            listing_price=pricing["listing_price"],
            market_avg_price=pricing.get("market_avg"),
            price_warning=pricing.get("price_warning"),
            suggested_price=pricing.get("suggested_price"),
            local_images=json.dumps(processed),
            retail_shipping_days=product.shipping_days or 5,
            listing_shipping_days=(product.shipping_days or 5) * SHIPPING_MULTIPLIER,
            handling_days=DEFAULT_HANDLING,
            quality_score=quality["total"],
            quality_breakdown=json.dumps(quality["breakdown"]),
            improvement_tips=json.dumps(quality["improvement_tips"]),
            vero_risk_level=vero["risk_level"],
            ebay_fee=pricing["ebay_fee"],
            paypal_fee=pricing["paypal_fee"],
            net_profit=pricing["net_profit"],
            status="draft",
        )
        db.add(listing)
        db.commit()
        db.refresh(listing)
        return {"success": True, "listing": listing.to_dict(), "pricing": pricing, "vero": vero}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error_type": "scrape_failed", "message": str(e)})


@app.patch("/api/listings/{listing_id}")
def patch_listing(listing_id: int, payload: dict, db: Session = Depends(get_db)):
    item = db.query(Listing).filter(Listing.id == listing_id).first()
    if not item:
        raise HTTPException(404, "Listing not found")
    for k, v in payload.items():
        if hasattr(item, k):
            setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return {"success": True, "listing": item.to_dict()}


@app.delete("/api/listings/{listing_id}")
def delete_listing(listing_id: int, db: Session = Depends(get_db)):
    item = db.query(Listing).filter(Listing.id == listing_id).first()
    if not item:
        raise HTTPException(404, "Listing not found")
    db.delete(item)
    db.commit()
    return {"success": True}


@app.get("/api/ebay/auth-url")
def auth_url():
    return {"success": True, "url": ebay_api.get_auth_url()}


@app.get("/ebay/callback")
def ebay_callback(code: str = ""):
    ebay_api.exchange_code_for_token(code)
    return RedirectResponse(url="/dashboard", status_code=302)


@app.post("/api/scanner/run")
def run_scanner(db: Session = Depends(get_db)):
    results = scan_all_targets(db)
    return {"success": True, "count": len(results)}


@app.get("/api/scanner/top")
def scanner_top(db: Session = Depends(get_db)):
    rows = db.query(ScannerResult).order_by(ScannerResult.profit_margin_pct.desc()).limit(5).all()
    return {"success": True, "results": [{"id": r.id, "product_name": r.product_name, "profit_margin_pct": r.profit_margin_pct, "retail_url": r.retail_url} for r in rows]}


@app.get("/api/listings/{listing_id}/export/{fmt}")
def export_listing(listing_id: int, fmt: str, db: Session = Depends(get_db)):
    l = db.query(Listing).filter(Listing.id == listing_id).first()
    if not l:
        raise HTTPException(404, "Listing not found")
    l.export_count = (l.export_count or 0) + 1
    db.commit()
    if fmt == "amazon": return Response(export_amazon(l), media_type="text/csv")
    if fmt == "etsy": return Response(export_etsy(l), media_type="text/csv")
    if fmt == "facebook": return Response(export_facebook(l), media_type="application/json")
    if fmt == "csv": return Response(export_generic_csv(l), media_type="text/csv")
    raise HTTPException(400, "Unsupported format")


@app.get("/api/listings/export/bulk")
def export_bulk(ids: str, db: Session = Depends(get_db)):
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    rows = db.query(Listing).filter(Listing.id.in_(id_list)).all()
    return Response(export_bulk_zip(rows), media_type="application/zip")


@app.websocket("/ws/bulk-progress")
async def bulk_progress_ws(websocket: WebSocket):
    await websocket.accept()
    data = await websocket.receive_json()
    urls = data.get("urls", [])
    markup = float(data.get("markup", DEFAULT_MARKUP))
    await websocket.send_json({"type": "start", "total": len(urls), "url": ""})
    success = 0
    for i, url in enumerate(urls, start=1):
        await websocket.send_json({"type": "progress", "current": i, "total": len(urls), "url": url, "status": "scraping"})
        p = scrape_product_sync(url)
        if p.error:
            await websocket.send_json({"type": "error", "url": url, "error_type": p.error.error_type, "message": p.error.message})
            continue
        await websocket.send_json({"type": "progress", "current": i, "total": len(urls), "url": url, "status": "done"})
        success += 1
        await websocket.send_json({"type": "listing_ready", "listing": {"title": p.title, "source_url": url, "est_price": calculate_price(p.price or 0, p.title, markup)["listing_price"]}})
    await websocket.send_json({"type": "complete", "succeeded": success, "failed": len(urls)-success})
