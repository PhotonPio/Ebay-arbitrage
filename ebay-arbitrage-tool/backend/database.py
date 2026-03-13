import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config.settings import DB_PATH

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Listing(Base):
    __tablename__ = "listings"
    id = Column(Integer, primary_key=True)
    source_url = Column(String, nullable=False)
    raw_title = Column(String)
    raw_brand = Column(String)
    raw_price = Column(Float)
    raw_description = Column(Text)
    raw_specs = Column(Text, default="{}")
    raw_images = Column(Text, default="[]")
    ebay_title = Column(String(80))
    ebay_description = Column(Text)
    listing_price = Column(Float)
    market_avg_price = Column(Float)
    price_warning = Column(Boolean, default=False)
    suggested_price = Column(Float)
    local_images = Column(Text, default="[]")
    retail_shipping_days = Column(Integer)
    listing_shipping_days = Column(Integer)
    handling_days = Column(Integer, default=2)
    quality_score = Column(Integer, default=0)
    quality_breakdown = Column(Text, default="{}")
    improvement_tips = Column(Text, default="[]")
    vero_risk_level = Column(String, default="unknown")
    ebay_fee = Column(Float)
    paypal_fee = Column(Float)
    net_profit = Column(Float)
    export_count = Column(Integer, default=0)
    ebay_listing_id = Column(String)
    published = Column(Boolean, default=False)
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "source_url": self.source_url,
            "raw_title": self.raw_title,
            "raw_brand": self.raw_brand,
            "raw_price": self.raw_price,
            "raw_description": self.raw_description,
            "raw_specs": json.loads(self.raw_specs or "{}"),
            "raw_images": json.loads(self.raw_images or "[]"),
            "ebay_title": self.ebay_title,
            "ebay_description": self.ebay_description,
            "listing_price": self.listing_price,
            "market_avg_price": self.market_avg_price,
            "price_warning": self.price_warning,
            "suggested_price": self.suggested_price,
            "local_images": json.loads(self.local_images or "[]"),
            "quality_score": self.quality_score,
            "quality_breakdown": json.loads(self.quality_breakdown or "{}"),
            "improvement_tips": json.loads(self.improvement_tips or "[]"),
            "vero_risk_level": self.vero_risk_level,
            "ebay_fee": self.ebay_fee,
            "paypal_fee": self.paypal_fee,
            "net_profit": self.net_profit,
            "published": self.published,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScannerResult(Base):
    __tablename__ = "scanner_results"
    id = Column(Integer, primary_key=True)
    brand = Column(String)
    product_name = Column(String)
    retail_price = Column(Float)
    retail_url = Column(String)
    image_url = Column(String)
    market_avg_price = Column(Float)
    profit_margin_pct = Column(Float)
    is_opportunity = Column(Boolean)
    vero_risk_level = Column(String, default="unknown")
    scanned_at = Column(DateTime, default=datetime.utcnow)


class ScannerTarget(Base):
    __tablename__ = "scanner_targets"
    id = Column(Integer, primary_key=True)
    brand = Column(String)
    url = Column(String)
    category = Column(String)
    enabled = Column(Boolean, default=True)
    last_scanned = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


def column_exists(engine, table, column):
    with engine.connect() as conn:
        result = conn.execute(text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in result)


def run_migrations():
    columns = [
        ("vero_risk_level", "TEXT DEFAULT 'unknown'"),
        ("ebay_fee", "REAL"),
        ("paypal_fee", "REAL"),
        ("net_profit", "REAL"),
        ("quality_breakdown", "TEXT DEFAULT '{}'"),
        ("improvement_tips", "TEXT DEFAULT '[]'"),
        ("export_count", "INTEGER DEFAULT 0"),
    ]
    with engine.begin() as conn:
        for name, ddl in columns:
            if not column_exists(engine, "listings", name):
                conn.execute(text(f"ALTER TABLE listings ADD COLUMN {name} {ddl}"))


def seed_scanner_targets():
    defaults = [
        {"brand": "Versace", "url": "https://www.versace.com/us/en/men/accessories/watches/", "category": "Watches"},
        {"brand": "Omega", "url": "https://www.omegawatches.com/watches/", "category": "Watches"},
        {"brand": "Ray-Ban", "url": "https://www.ray-ban.com/usa/sunglasses", "category": "Sunglasses"},
        {"brand": "Gucci", "url": "https://www.gucci.com/us/en/ca/accessories/watches-c-accessorieswatches", "category": "Watches"},
    ]
    db = SessionLocal()
    try:
        if db.query(ScannerTarget).count() == 0:
            db.add_all([ScannerTarget(**item) for item in defaults])
            db.commit()
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    run_migrations()
    seed_scanner_targets()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
