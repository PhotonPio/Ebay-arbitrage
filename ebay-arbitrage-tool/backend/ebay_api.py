from config.settings import DEMO_MODE, EBAY_REDIRECT_URI


def get_auth_url():
    return f"https://auth.ebay.com/oauth2/authorize?redirect_uri={EBAY_REDIRECT_URI}"


def exchange_code_for_token(code: str):
    if DEMO_MODE:
        return {"access_token": f"demo_token_{code[-5:]}", "expires_in": 7200}
    return {"access_token": "live_token", "expires_in": 7200}


def publish_listing(listing: dict):
    if DEMO_MODE:
        return {"success": True, "listing_id": f"DEMO-{listing.get('id', 0)}", "demo": True}
    return {"success": True, "listing_id": "LIVE-123", "demo": False}
