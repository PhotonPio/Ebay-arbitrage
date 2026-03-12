"""
eBay API Integration
Handles OAuth flow, listing creation, image upload.
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
)

# Scopes required for listing
SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
]


# ── OAuth ─────────────────────────────────────────────────────────────────────

def get_auth_url() -> str:
    """Return the URL to redirect the user for eBay OAuth consent."""
    params = urllib.parse.urlencode({
        "client_id": EBAY_CLIENT_ID,
        "redirect_uri": EBAY_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
    })
    return f"{EBAY_AUTH_BASE}/oauth2/authorize?{params}"


def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
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


# ── Image Upload (Trading API) ────────────────────────────────────────────────

def upload_image(access_token: str, image_path: str) -> Optional[str]:
    """
    Upload a local image to eBay using UploadSiteHostedPictures.
    Returns the hosted image URL or None on failure.
    """
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


# ── Inventory API — create/publish listing ───────────────────────────────────

def create_inventory_item(access_token: str, listing: dict, ebay_image_urls: list) -> dict:
    """Create an inventory item via Inventory API. Returns API response."""
    sku = f"ARBT-{listing['id']}"

    payload = {
        "availability": {
            "shipToLocationAvailability": {"quantity": 1}
        },
        "condition": "NEW",
        "product": {
            "title": listing.get("ebay_title", ""),
            "description": listing.get("ebay_description", ""),
            "imageUrls": ebay_image_urls or [],
            "aspects": {
                k: [str(v)]
                for k, v in (listing.get("raw_specs") or {}).items()
            },
        },
    }

    resp = httpx.put(
        f"{EBAY_API_BASE}/sell/inventory/v1/inventory_item/{sku}",
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=15,
    )
    return {"status": resp.status_code, "body": resp.text, "sku": sku}


def create_offer(access_token: str, listing: dict, sku: str) -> dict:
    """Create an eBay offer for the inventory item."""
    payload = {
        "sku": sku,
        "marketplaceId": "EBAY_US",
        "format": "FIXED_PRICE",
        "availableQuantity": 1,
        "pricingSummary": {
            "price": {
                "currency": "USD",
                "value": str(listing.get("listing_price", "0.00")),
            }
        },
        "listingPolicies": {},   # Seller must configure policies in eBay seller hub
        "fulfillmentPolicyId": "",
        "paymentPolicyId": "",
        "returnPolicyId": "",
        "storeCategoryNames": [],
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
    resp = httpx.post(
        f"{EBAY_API_BASE}/sell/inventory/v1/offer/{offer_id}/publish",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    data = resp.json()
    return {"status": resp.status_code, "listing_id": data.get("listingId"), "body": data}
