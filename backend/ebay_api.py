"""
backend/ebay_api.py
eBay Trading API and Browse API integration.
Handles OAuth, image upload, and listing creation.

eBay API Docs:
  Trading API:  https://developer.ebay.com/api-docs/user-guides/static/trading-ug/trading-api-guide.html
  Browse API:   https://developer.ebay.com/api-docs/buy/browse/overview.html
"""
import base64
import hashlib
import logging
import xml.etree.ElementTree as ET
from typing import Optional, Dict, List
from pathlib import Path

import httpx

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import get_settings
from backend.image_processor import ImageProcessor

logger = logging.getLogger(__name__)
settings = get_settings()
image_processor = ImageProcessor()


class EbayAPI:
    """eBay API client — Trading API for listing creation + image upload."""

    # ── XML Trading API ────────────────────────────────────────────────────

    def _trading_headers(self, call_name: str) -> Dict:
        return {
            "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
            "X-EBAY-API-DEV-NAME": settings.ebay_dev_id,
            "X-EBAY-API-APP-NAME": settings.ebay_active_app_id,
            "X-EBAY-API-CERT-NAME": settings.ebay_active_cert_id,
            "X-EBAY-API-CALL-NAME": call_name,
            "X-EBAY-API-SITEID": "0",
            "Content-Type": "text/xml",
        }

    async def _trading_call(self, call_name: str, xml_body: str) -> ET.Element:
        """Make a Trading API XML call."""
        payload = f"""<?xml version="1.0" encoding="utf-8"?>
<{call_name}Request xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials>
    <eBayAuthToken>{settings.ebay_active_token}</eBayAuthToken>
  </RequesterCredentials>
  {xml_body}
</{call_name}Request>"""

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                settings.ebay_trading_url,
                content=payload.encode("utf-8"),
                headers=self._trading_headers(call_name),
            )
        root = ET.fromstring(resp.text)
        return root

    # ── Image Upload ────────────────────────────────────────────────────────

    async def upload_image(self, local_path: str) -> Optional[str]:
        """
        Upload an image to eBay Picture Services.
        Returns the hosted picture URL on success.
        """
        img_bytes = image_processor.get_image_bytes(local_path)
        if not img_bytes:
            logger.error(f"Image not found: {local_path}")
            return None

        # Multipart MIME for UploadSiteHostedPictures
        boundary = "------EbayArbitrageImageBoundary"
        body_parts = []

        xml_part = (
            f"--{boundary}\r\n"
            "Content-Disposition: form-data; name='XML Payload'\r\n"
            "Content-Type: text/xml;charset=utf-8\r\n\r\n"
            f"""<?xml version="1.0" encoding="utf-8"?>
<UploadSiteHostedPicturesRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials>
    <eBayAuthToken>{settings.ebay_active_token}</eBayAuthToken>
  </RequesterCredentials>
  <PictureName>product_image</PictureName>
  <PictureSet>Supersize</PictureSet>
</UploadSiteHostedPicturesRequest>\r\n"""
        )
        body_parts.append(body_part.encode("utf-8") if isinstance(xml_part, str) else xml_part)
        body_parts.append(xml_part.encode("utf-8"))

        img_part_header = (
            f"--{boundary}\r\n"
            "Content-Disposition: form-data; name='image'; filename='image.jpg'\r\n"
            "Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8")
        body_parts = [xml_part.encode("utf-8"), img_part_header, img_bytes,
                     f"\r\n--{boundary}--\r\n".encode("utf-8")]
        body = b"".join(body_parts)

        headers = {
            **self._trading_headers("UploadSiteHostedPictures"),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(settings.ebay_trading_url, content=body, headers=headers)
            root = ET.fromstring(resp.text)
            ns = "urn:ebay:apis:eBLBaseComponents"
            ack = root.findtext(f"{{{ns}}}Ack")
            if ack in ("Success", "Warning"):
                url = root.findtext(f".//{{{ns}}}FullURL")
                return url
            errors = root.findall(f".//{{{ns}}}ShortMessage")
            for e in errors:
                logger.error(f"eBay upload error: {e.text}")
        except Exception as e:
            logger.error(f"Image upload exception: {e}")
        return None

    # ── Create Listing ──────────────────────────────────────────────────────

    async def add_item(self, listing_data: Dict, ebay_image_urls: List[str]) -> Dict:
        """
        Create a listing on eBay using AddItem Trading API call.
        Returns dict with item_id and item_url on success.
        """
        if not settings.ebay_active_token:
            return {"success": False, "error": "eBay token not configured."}

        # Build picture URLs XML
        pics_xml = "".join(
            f"<PictureURL>{url}</PictureURL>" for url in ebay_image_urls[:12]
        )
        pics_block = f"<PictureDetails>{pics_xml}</PictureDetails>" if pics_xml else ""

        price = listing_data.get("ebay_price", 9.99)
        shipping_days = listing_data.get("ebay_shipping_days", 10)
        handling_days = listing_data.get("handling_days", 2)
        title = listing_data.get("ebay_title", "Item")[:80]
        description = listing_data.get("ebay_description", "See photos.")
        category_id = listing_data.get("ebay_category_id", "9355")

        xml_body = f"""
<Item>
  <Title>{self._escape(title)}</Title>
  <Description><![CDATA[{description}]]></Description>
  <PrimaryCategory>
    <CategoryID>{category_id}</CategoryID>
  </PrimaryCategory>
  <StartPrice>{price:.2f}</StartPrice>
  <CategoryMappingAllowed>true</CategoryMappingAllowed>
  <ConditionID>1000</ConditionID>
  <Country>US</Country>
  <Currency>USD</Currency>
  <DispatchTimeMax>{handling_days}</DispatchTimeMax>
  <ListingDuration>GTC</ListingDuration>
  <ListingType>FixedPriceItem</ListingType>
  <PaymentMethods>PayPal</PaymentMethods>
  <PayPalEmailAddress>placeholder@example.com</PayPalEmailAddress>
  <PostalCode>10001</PostalCode>
  <Quantity>1</Quantity>
  {pics_block}
  <ShippingDetails>
    <ShippingType>Flat</ShippingType>
    <ShippingServiceOptions>
      <ShippingServicePriority>1</ShippingServicePriority>
      <ShippingService>USPSMedia</ShippingService>
      <ShippingServiceCost>0.00</ShippingServiceCost>
      <ShippingTimeMin>1</ShippingTimeMin>
      <ShippingTimeMax>{shipping_days}</ShippingTimeMax>
    </ShippingServiceOptions>
  </ShippingDetails>
  <ReturnPolicy>
    <ReturnsAcceptedOption>ReturnsAccepted</ReturnsAcceptedOption>
    <RefundOption>MoneyBack</RefundOption>
    <ReturnsWithinOption>Days_30</ReturnsWithinOption>
    <ShippingCostPaidByOption>Buyer</ShippingCostPaidByOption>
  </ReturnPolicy>
</Item>"""

        try:
            root = await self._trading_call("AddItem", xml_body)
            ns = "urn:ebay:apis:eBLBaseComponents"
            ack = root.findtext(f"{{{ns}}}Ack")
            if ack in ("Success", "Warning"):
                item_id = root.findtext(f"{{{ns}}}ItemID")
                domain = "sandbox.ebay.com" if settings.ebay_environment == "sandbox" else "www.ebay.com"
                return {
                    "success": True,
                    "item_id": item_id,
                    "item_url": f"https://{domain}/itm/{item_id}",
                }
            errors = root.findall(f".//{{{ns}}}ShortMessage")
            error_msgs = [e.text for e in errors]
            return {"success": False, "error": "; ".join(error_msgs)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _escape(self, text: str) -> str:
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    async def verify_credentials(self) -> Dict:
        """Test eBay API credentials by calling GeteBayOfficialTime."""
        if not settings.ebay_active_token:
            return {"valid": False, "message": "No eBay token configured."}
        try:
            root = await self._trading_call("GeteBayOfficialTime", "")
            ns = "urn:ebay:apis:eBLBaseComponents"
            ack = root.findtext(f"{{{ns}}}Ack")
            timestamp = root.findtext(f"{{{ns}}}Timestamp")
            if ack in ("Success", "Warning"):
                return {"valid": True, "message": f"Connected to eBay ({settings.ebay_environment}). Server time: {timestamp}"}
            errors = [e.text for e in root.findall(f".//{{{ns}}}ShortMessage")]
            return {"valid": False, "message": "; ".join(errors)}
        except Exception as e:
            return {"valid": False, "message": str(e)}
