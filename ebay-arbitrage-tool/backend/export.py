import csv
import io
import json
import zipfile


def _csv_bytes(headers, rows):
    s = io.StringIO()
    w = csv.DictWriter(s, fieldnames=headers)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return s.getvalue().encode()


def export_amazon(listing):
    row = {
        "item_sku": f"FF-{listing.id}", "item_name": listing.ebay_title, "brand_name": listing.raw_brand,
        "bullet_point1": listing.raw_title, "bullet_point2": "", "bullet_point3": "", "bullet_point4": "", "bullet_point5": "",
        "description": listing.ebay_description, "standard_price": listing.listing_price or 0, "quantity": 1,
        "main_image_url": (json.loads(listing.raw_images or '[]')+[""])[0],
        "other_image_url1": "", "other_image_url2": "", "other_image_url3": "", "other_image_url4": "", "other_image_url5": "", "other_image_url6": "", "other_image_url7": "",
    }
    return _csv_bytes(list(row.keys()), [row])


def export_etsy(listing):
    row = {"title": listing.ebay_title, "description": listing.ebay_description, "price": listing.listing_price or 0, "quantity": 1, "tags": "arbitrage,reseller", "primary_color": "", "secondary_color": "", "materials": "", **{f"image{i}":"" for i in range(1,11)}}
    return _csv_bytes(list(row.keys()), [row])


def export_facebook(listing):
    return json.dumps({"title": listing.ebay_title, "description": listing.ebay_description, "price": listing.listing_price, "images": json.loads(listing.raw_images or "[]")}).encode()


def export_generic_csv(listing):
    data = listing.to_dict()
    return _csv_bytes(list(data.keys()), [data])


def export_bulk_zip(listings):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w', zipfile.ZIP_DEFLATED) as z:
        for l in listings:
            z.writestr(f"listing_{l.id}_amazon.csv", export_amazon(l))
            z.writestr(f"listing_{l.id}_etsy.csv", export_etsy(l))
            z.writestr(f"listing_{l.id}_facebook.json", export_facebook(l))
            z.writestr(f"listing_{l.id}_generic.csv", export_generic_csv(l))
    return b.getvalue()
