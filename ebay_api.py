"""
eBay API Integration
Handles OAuth flow, listing creation, image upload.
In DEMO_MODE, all calls return realistic mock responses so you can
test the full workflow without real eBay credentials.
"""
import sys
import json
import base64
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import (
    EBAY_CLIENT_ID, EBAY_CLIENT_SECRET,
    EBAY_REDIRECT_URI, EBAY_API_BASE, EBAY_AUTH_BASE, EBAY_ENV,
    DEMO_MODE,
)

SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
]


# ── OAuth ─────────────────────────────────────────────────────────────────────

def get_auth_url() -> str:
    if DEMO_MODE:
        # In demo mode, redirect straight back with a fake code
        return "/ebay/callback?code=DEMO_CODE_12345&demo=true"

    params = urllib.parse.urlencode({
        "client_id": EBAY_CLIENT_ID,
        "redirect_uri": EBAY_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
    })
    return f"{EBAY_AUTH_BASE}/oauth2/authorize?{params}"


def exchange_code_for_token(code: str) -> dict:
    if DEMO_MODE or code == "DEMO_CODE_12345":
        return {
            "access_token": "DEMO_ACCESS_TOKEN",
            "refresh_token": "DEMO_REFRESH_TOKEN",
            "expires_in": 7200,
            "token_type": "User Access Token",
            "demo": True,
        }

    creds = base64.b64encode(f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()).decode()
    resp = httpx.post(
        f"{EBAY_API_BASE}/identity/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": EBAY_REDIRECT_URI,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    if DEMO_MODE:
        return {"access_token": "DEMO_ACCESS_TOKEN", "expires_in": 7200}

    creds = base64.b64encode(f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()).decode()
    resp = httpx.post(
        f"{EBAY_API_BASE}/identity/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ── Image Upload ──────────────────────────────────────────────────────────────

def upload_image(access_token: str, image_path: str) -> Optional[str]:
    if DEMO_MODE or access_token == "DEMO_ACCESS_TOKEN":
        # Return a placeholder image URL for demo
        return f"https://via.placeholder.com/1600x1600/f5f5f5/333333?text=Product+Image"

    path = Path(image_path)
    if not path.exists():
        print(f"⚠ Image not found: {image_path}")
        return None

    with open(path, "rb") as f:
        img_data = f.read()
    img_b64 = base64.b64encode(img_data).decode()

    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<UploadSiteHostedPicturesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials>
    <eBayAuthToken>{access_token}</eBayAuthToken>
  </RequesterCredentials>
  <PictureData contentType="image/jpeg">{img_b64}</PictureData>
  <PictureName>{path.stem}</PictureName>
  <PictureSet>Supersize</PictureSet>
</UploadSiteHostedPicturesRequest>"""

    trading_url = (
        "https://api.ebay.com/ws/api.dll"
        if EBAY_ENV == "production"
        else "https://api.sandbox.ebay.com/ws/api.dll"
    )

    try:
        resp = httpx.post(
            trading_url,
            content=xml_body.encode("utf-8"),
            headers={
                "Content-Type": "text/xml",
                "X-EBAY-API-SITEID": "0",
                "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
                "X-EBAY-API-CALL-NAME": "UploadSiteHostedPictures",
                "X-EBAY-API-APP-NAME": EBAY_CLIENT_ID,
            },
            timeout=30,
        )
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        ns = {"eb": "urn:ebay:apis:eBLBaseComponents"}
        url_el = root.find(".//eb:FullURL", ns)
        if url_el is not None:
            return url_el.text
    except Exception as e:
        print(f"⚠ eBay image upload error: {e}")

    return None


# ── Inventory API ─────────────────────────────────────────────────────────────

def create_inventory_item(access_token: str, listing: dict, ebay_image_urls: list) -> dict:
    if DEMO_MODE or access_token == "DEMO_ACCESS_TOKEN":
        sku = f"DEMO-ARBT-{listing['id']}"
        return {"status": 204, "body": "Demo inventory item created", "sku": sku}

    sku = f"ARBT-{listing['id']}"
    payload = {
        "availability": {"shipToLocationAvailability": {"quantity": 1}},
        "condition": "NEW",
        "product": {
            "title": listing.get("ebay_title", ""),
            "description": listing.get("ebay_description", ""),
            "imageUrls": ebay_image_urls or [],
            "aspects": {k: [str(v)] for k, v in (listing.get("raw_specs") or {}).items()},
        },
    }
    resp = httpx.put(
        f"{EBAY_API_BASE}/sell/inventory/v1/inventory_item/{sku}",
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    return {"status": resp.status_code, "body": resp.text, "sku": sku}


def create_offer(access_token: str, listing: dict, sku: str) -> dict:
    if DEMO_MODE or access_token == "DEMO_ACCESS_TOKEN":
        return {"status": 201, "offer_id": f"DEMO-OFFER-{listing['id']}", "body": {}}

    payload = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "availableQuantity": 1,
        "pricingSummary": {
            "price": {"currency": "USD", "value": str(listing.get("listing_price", "0.00"))}
        },
        "listingPolicies": {},
    }
    resp = httpx.post(
        f"{EBAY_API_BASE}/sell/inventory/v1/offer",
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=15,
    )
    data = resp.json()
    return {"status": resp.status_code, "offer_id": data.get("offerId"), "body": data}


def publish_offer(access_token: str, offer_id: str) -> dict:
    if DEMO_MODE or access_token == "DEMO_ACCESS_TOKEN":
        return {
            "status": 200,
            "listing_id": f"DEMO-LISTING-{offer_id}",
            "body": {"demo": True, "message": "Listing simulated — no real eBay listing created"},
        }

    resp = httpx.post(
        f"{EBAY_API_BASE}/sell/inventory/v1/offer/{offer_id}/publish",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    data = resp.json()
    return {"status": resp.status_code, "listing_id": data.get("listingId"), "body": data}
