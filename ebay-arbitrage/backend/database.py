"""
backend/database.py
SQLAlchemy async models and database initialization.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, DateTime, Text, Boolean, JSON
from datetime import datetime
from typing import Optional
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Source
    source_url: Mapped[str] = mapped_column(String(2000))
    source_site: Mapped[Optional[str]] = mapped_column(String(100))

    # Product data (raw)
    raw_title: Mapped[Optional[str]] = mapped_column(String(500))
    raw_brand: Mapped[Optional[str]] = mapped_column(String(200))
    raw_description: Mapped[Optional[str]] = mapped_column(Text)
    raw_price: Mapped[Optional[float]] = mapped_column(Float)
    raw_specs: Mapped[Optional[str]] = mapped_column(JSON)
    raw_images: Mapped[Optional[str]] = mapped_column(JSON)  # list of URLs
    raw_shipping_days: Mapped[Optional[int]] = mapped_column(Integer)

    # Generated eBay listing
    ebay_title: Mapped[Optional[str]] = mapped_column(String(80))
    ebay_description: Mapped[Optional[str]] = mapped_column(Text)
    ebay_price: Mapped[Optional[float]] = mapped_column(Float)
    ebay_shipping_days: Mapped[Optional[int]] = mapped_column(Integer)
    handling_days: Mapped[int] = mapped_column(Integer, default=2)
    ebay_category_id: Mapped[Optional[str]] = mapped_column(String(20))

    # Pricing
    markup_percent: Mapped[float] = mapped_column(Float, default=0.80)
    market_avg_price: Mapped[Optional[float]] = mapped_column(Float)
    price_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_price: Mapped[Optional[float]] = mapped_column(Float)

    # Images (local paths)
    processed_images: Mapped[Optional[str]] = mapped_column(JSON)

    # Quality
    quality_score: Mapped[Optional[int]] = mapped_column(Integer)
    quality_breakdown: Mapped[Optional[str]] = mapped_column(JSON)

    # eBay publish status
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # draft | ready | published | failed
    ebay_listing_id: Mapped[Optional[str]] = mapped_column(String(50))
    ebay_item_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Profit tracking
    profit_amount: Mapped[Optional[float]] = mapped_column(Float)
    profit_margin: Mapped[Optional[float]] = mapped_column(Float)


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session
