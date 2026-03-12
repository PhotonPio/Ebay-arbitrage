"""
Database layer — SQLite via SQLAlchemy (sync)
"""
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, Text, Boolean, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ── resolve DB path ──────────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine  = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Session_ = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base    = declarative_base()


# ── Models ───────────────────────────────────────────────────────────────────

class Listing(Base):
    __tablename__ = "listings"

    id              = Column(Integer, primary_key=True, index=True)
    source_url      = Column(String, nullable=False)

    # raw scraped data
    raw_title       = Column(String)
    raw_brand       = Column(String)
    raw_price       = Column(Float)
    raw_description = Column(Text)
    raw_specs       = Column(Text)       # JSON string
    raw_images      = Column(Text)       # JSON list of URLs

    # generated listing
    ebay_title      = Column(String(80))
    ebay_description= Column(Text)
    listing_price   = Column(Float)
    market_avg_price= Column(Float)
    price_warning   = Column(Boolean, default=False)
    suggested_price = Column(Float)

    # images (local processed)
    local_images    = Column(Text)       # JSON list of local paths

    # shipping
    retail_shipping_days = Column(Integer)
    listing_shipping_days= Column(Integer)
    handling_days   = Column(Integer, default=2)

    # quality
    quality_score   = Column(Integer, default=0)

    # ebay
    ebay_listing_id = Column(String)
    ebay_draft_id   = Column(String)
    published       = Column(Boolean, default=False)
    published_at    = Column(DateTime)

    # meta
    status          = Column(String, default="draft")   # draft | published | error
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def raw_specs_dict(self):
        try:
            return json.loads(self.raw_specs or "{}")
        except Exception:
            return {}

    def images_list(self):
        try:
            return json.loads(self.raw_images or "[]")
        except Exception:
            return []

    def local_images_list(self):
        try:
            return json.loads(self.local_images or "[]")
        except Exception:
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "source_url": self.source_url,
            "raw_title": self.raw_title,
            "raw_brand": self.raw_brand,
            "raw_price": self.raw_price,
            "raw_description": self.raw_description,
            "raw_specs": self.raw_specs_dict(),
            "raw_images": self.images_list(),
            "ebay_title": self.ebay_title,
            "ebay_description": self.ebay_description,
            "listing_price": self.listing_price,
            "market_avg_price": self.market_avg_price,
            "price_warning": self.price_warning,
            "suggested_price": self.suggested_price,
            "local_images": self.local_images_list(),
            "retail_shipping_days": self.retail_shipping_days,
            "listing_shipping_days": self.listing_shipping_days,
            "handling_days": self.handling_days,
            "quality_score": self.quality_score,
            "ebay_listing_id": self.ebay_listing_id,
            "published": self.published,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def get_db() -> Session:
    db = Session_()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅  Database initialized")
