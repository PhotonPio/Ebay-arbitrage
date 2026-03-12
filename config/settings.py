"""
config/settings.py
Application-wide settings loaded from environment variables.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str = ""
    ebay_app_id: str = ""
    ebay_cert_id: str = ""
    ebay_dev_id: str = ""
    ebay_user_token: str = ""
    ebay_sandbox_app_id: str = ""
    ebay_sandbox_cert_id: str = ""
    ebay_sandbox_user_token: str = ""

    # eBay Environment
    ebay_environment: str = "sandbox"  # sandbox | production

    # Pricing
    default_markup: float = 0.80
    price_warning_threshold: float = 0.20

    # App
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    debug: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./database/listings.db"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def ebay_active_app_id(self) -> str:
        if self.ebay_environment == "production":
            return self.ebay_app_id
        return self.ebay_sandbox_app_id

    @property
    def ebay_active_cert_id(self) -> str:
        if self.ebay_environment == "production":
            return self.ebay_cert_id
        return self.ebay_sandbox_cert_id

    @property
    def ebay_active_token(self) -> str:
        if self.ebay_environment == "production":
            return self.ebay_user_token
        return self.ebay_sandbox_user_token

    @property
    def ebay_base_url(self) -> str:
        if self.ebay_environment == "production":
            return "https://api.ebay.com"
        return "https://api.sandbox.ebay.com"

    @property
    def ebay_trading_url(self) -> str:
        if self.ebay_environment == "production":
            return "https://api.ebay.com/ws/api.dll"
        return "https://api.sandbox.ebay.com/ws/api.dll"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
