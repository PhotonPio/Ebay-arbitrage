"""
backend/models.py
Pydantic request/response models.
"""
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime


class ScrapeRequest(BaseModel):
    url: str
    markup: Optional[float] = 0.80


class BulkScrapeRequest(BaseModel):
    urls: List[str]
    markup: Optional[float] = 0.80


class ScrapedProduct(BaseModel):
    title: str
    brand: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    specs: Optional[Dict[str, str]] = None
    images: Optional[List[str]] = []
    shipping_days: Optional[int] = None
    source_url: str
    source_site: Optional[str] = None


class PriceCheckResult(BaseModel):
    market_avg: Optional[float]
    market_min: Optional[float]
    market_max: Optional[float]
    sample_count: int
    your_price: float
    warning: bool
    suggested_price: Optional[float]
    message: str


class QualityBreakdown(BaseModel):
    title_score: int       # 0-25
    description_score: int # 0-25
    image_score: int       # 0-25
    price_score: int       # 0-25
    total: int             # 0-100


class GeneratedListing(BaseModel):
    listing_id: int
    ebay_title: str
    ebay_description: str
    ebay_price: float
    ebay_shipping_days: int
    handling_days: int
    processed_images: List[str]
    quality_score: int
    quality_breakdown: QualityBreakdown
    price_check: PriceCheckResult
    status: str


class EditListingRequest(BaseModel):
    listing_id: int
    ebay_title: Optional[str] = None
    ebay_description: Optional[str] = None
    ebay_price: Optional[float] = None
    ebay_shipping_days: Optional[int] = None
    handling_days: Optional[int] = None


class PublishRequest(BaseModel):
    listing_id: int


class ListingResponse(BaseModel):
    id: int
    created_at: datetime
    source_url: str
    source_site: Optional[str]
    raw_title: Optional[str]
    raw_price: Optional[float]
    ebay_title: Optional[str]
    ebay_price: Optional[float]
    ebay_shipping_days: Optional[int]
    quality_score: Optional[int]
    status: str
    ebay_listing_id: Optional[str]
    ebay_item_url: Optional[str]
    profit_amount: Optional[float]
    profit_margin: Optional[float]
    processed_images: Optional[List[str]]

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_listings: int
    published_listings: int
    draft_listings: int
    avg_profit_margin: float
    total_estimated_profit: float
    recent_listings: List[ListingResponse]
    top_quality_score: int
