import json
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import ebay_api
from backend.database import Base, Listing, ScannerResult, ScannerTarget, column_exists
from backend.listing_generator import calculate_quality_score, generate_ebay_title
from backend.main import app
from backend.pricing_engine import calculate_price
from backend.scraper import _extract_price, _extract_shipping_days, _parse_generic
from backend.vero_checker import check_brand
from bs4 import BeautifulSoup


class UnitTests(unittest.TestCase):
    def test_extract_price_cases(self):
        cases = {
            "$1,299.00": 1299.0, "£89": 89.0, "was $200 now $150": 200.0, "Free": None,
            "EUR 10.99": 10.99, "99": 99.0, "$0.99": 0.99, "": None, "$12,345": 12345.0, "CAD $17.50": 17.5,
        }
        for raw, expected in cases.items():
            self.assertEqual(_extract_price(raw), expected)

    def test_shipping_days_cases(self):
        cases = {"3-5 days":5, "2 to 4 business days":4, "Arrives in 7 days":7, "next day":None, "10–14 days":14, "1 day":1, "":None, "ships in 12 business days":12}
        for raw, expected in cases.items():
            self.assertEqual(_extract_shipping_days(raw), expected)

    def test_title_quality_price_vero_parse(self):
        t = generate_ebay_title("New Super Shoe Free Shipping", "Nike", {"Color":"Black"})
        self.assertLessEqual(len(t), 80)
        self.assertEqual(t.lower().count("nike"), 1)
        q = calculate_quality_score("Nike Great Running Shoes Mens Black Size 10", "Product Overview Key Features Technical Specifications Shipping & Handling Seller Guarantee " + ("word "*160), ["a","b","c","d","e"], 100, 95, {"a":1,"b":2,"c":3,"d":4,"e":5})
        self.assertIn(q["grade"], {"A","B","C","D","F"})
        self.assertEqual(calculate_quality_score("x"*45, "x", [], 100, 100, {})["grade"], "D")
        price = calculate_price(100, "Item", 0.8)
        self.assertAlmostEqual(price["listing_price"], 180)
        self.assertTrue("fees_breakdown" in price)
        self.assertEqual(check_brand("Gucci")["risk_level"], "high")
        self.assertEqual(check_brand("Omega")["risk_level"], "medium")
        self.assertEqual(check_brand("Random")["risk_level"], "low")
        self.assertEqual(check_brand("")["risk_level"], "unknown")

        html = "<html><head><meta property='og:title' content='Test Product'></head><body><div class='price'>$19.99</div><div itemprop='description'><ul><li>A</li></ul></div><img src='https://x.com/a.jpg'></body></html>"
        p = _parse_generic(BeautifulSoup(html, "html.parser"), "https://example.com/p")
        self.assertEqual(p.title, "Test Product")
        self.assertEqual(p.price, 19.99)
        self.assertTrue(p.images)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_crud_and_types(self):
        db = self.Session()
        l = Listing(source_url="https://x.com", raw_specs=json.dumps({"a":1}), raw_images=json.dumps(["i"]), local_images=json.dumps(["l"]))
        db.add(l); db.commit(); db.refresh(l)
        self.assertEqual(l.to_dict()["raw_specs"], {"a":1})
        self.assertEqual(l.to_dict()["raw_images"], ["i"])
        l.raw_title = "updated"; db.commit()
        self.assertEqual(db.query(Listing).first().raw_title, "updated")
        db.delete(l); db.commit(); self.assertEqual(db.query(Listing).count(), 0)

    def test_scanner_tables(self):
        db=self.Session(); db.add(ScannerTarget(brand="B",url="u",category="c")); db.add(ScannerResult(product_name="p")); db.commit()
        self.assertEqual(db.query(ScannerTarget).count(),1)
        self.assertEqual(db.query(ScannerResult).count(),1)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_core_endpoints(self):
        r=self.client.get('/'); self.assertEqual(r.status_code,200); self.assertIn('FLIP', r.text); self.assertIn('FORGE', r.text)
        r=self.client.get('/api/status'); self.assertEqual(r.status_code,200); body=r.json(); self.assertTrue(body['demo_mode']);
        for k in ['demo_mode','ebay_configured','claude_configured','ebay_connected','version']: self.assertIn(k, body)
        self.assertEqual(self.client.get('/api/stats').status_code,200)
        lr=self.client.get('/api/listings'); self.assertEqual(lr.status_code,200); self.assertIsInstance(lr.json()['listings'], list)

    def test_errors_and_auth(self):
        r=self.client.post('/api/scrape', json={'url':'notaurl'})
        self.assertEqual(r.status_code,500); self.assertIn('error_type', r.json())
        self.assertEqual(self.client.patch('/api/listings/999', json={'ebay_title':'x'}).status_code,404)
        self.assertEqual(self.client.delete('/api/listings/999').status_code,404)
        au=self.client.get('/api/ebay/auth-url'); self.assertEqual(au.status_code,200); self.assertIn('/ebay/callback', au.json()['url'])
        cb=self.client.get('/ebay/callback?code=DEMO_CODE_12345', follow_redirects=False); self.assertEqual(cb.status_code,302)

    def test_demo_mode_stubs(self):
        tok=ebay_api.exchange_code_for_token('DEMO_CODE_12345'); self.assertIn('access_token', tok)
        p1=calculate_price(111.11,'A',0.8)['market_avg']; p2=calculate_price(111.11,'A',0.8)['market_avg']; self.assertEqual(p1,p2)
        res=ebay_api.publish_listing({'id':1}); self.assertTrue(res['success'])


if __name__ == '__main__':
    unittest.main()
