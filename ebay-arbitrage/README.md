# ⚡ ListingForge — eBay Arbitrage Automation Tool

Paste any retail product URL → AI generates an optimized eBay listing → Publish in one click.

---

## What It Does

1. **Scrapes** any retail website (Amazon, Walmart, Target, etc.) using Playwright
2. **Generates** an SEO-optimized eBay title and description using Claude AI
3. **Checks** current eBay market prices and warns if you're overpriced
4. **Processes** product images to eBay specifications automatically
5. **Calculates** your profit margin with configurable markup
6. **Publishes** directly to your eBay account via the official eBay API

---

## Screenshots

```
Main App → Paste URL → Pipeline runs automatically → Preview & edit → Publish
Dashboard → All listings, profit totals, quality scores
Preview → Full eBay-style preview with live editing
```

---

## Quick Start (5 minutes)

### Step 1 — Get the code

```bash
git clone <repo-url>
cd ebay-arbitrage-tool
```

### Step 2 — Run the setup script

```bash
chmod +x run.sh
./run.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Install Playwright (Chromium browser)
- Create the SQLite database
- Start the server

Then open: **http://localhost:8000**

### Step 3 — Add your API credentials

Copy the example environment file and fill it in:

```bash
cp .env.example .env
nano .env   # or use any text editor
```

---

## API Credentials Setup

### 1. Anthropic Claude API (for AI listing generation)

1. Go to [https://console.anthropic.com](https://console.anthropic.com)
2. Create an account or sign in
3. Go to **API Keys** → **Create new key**
4. Copy the key and paste it in `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

> **Without this key:** The tool still works — it uses a template-based listing generator as a fallback. Claude AI produces much better listings though.

---

### 2. eBay Developer API Credentials

> **Without eBay credentials:** You can still generate listings and preview them locally. You just can't publish to eBay.

#### Step-by-step:

1. Go to [https://developer.ebay.com](https://developer.ebay.com)
2. Click **Join** (free account)
3. Go to **My Account** → **Application Access**
4. Click **Create App Key**
5. Fill in:
   - **App Name**: `ListingForge` (or anything)
   - **Environment**: Start with **Sandbox** for testing

6. After creation, you'll see:
   ```
   App ID (Client ID):   YourApp-XXXXXXXX-sandbox-XXXXXXXX
   Cert ID (Secret):     sandbox-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   Dev ID:               XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
   ```

7. Paste them in `.env`:
   ```
   EBAY_SANDBOX_APP_ID=YourApp-XXXXXXXX-sandbox-XXXXXXXX
   EBAY_SANDBOX_CERT_ID=sandbox-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   EBAY_DEV_ID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
   EBAY_ENVIRONMENT=sandbox
   ```

#### Get a User Token (to post listings):

1. In the eBay Developer portal, go to **Get a User Token** (under your app)
2. Log in with your eBay sandbox account (or create one at [sandbox.ebay.com](https://sandbox.ebay.com))
3. Complete the OAuth flow
4. Copy the **User Access Token**:
   ```
   EBAY_SANDBOX_USER_TOKEN=AgAAAA...
   ```

#### Switch to Production:

Once tested, change `EBAY_ENVIRONMENT=production` and fill in your production credentials.

---

## Project Structure

```
ebay-arbitrage-tool/
│
├── backend/
│   ├── main.py              ← FastAPI app, all routes
│   ├── scraper.py           ← Playwright product scraper
│   ├── listing_generator.py ← Claude AI listing writer
│   ├── pricing_engine.py    ← Markup calc + market check
│   ├── image_processor.py   ← PIL image download + resize
│   ├── ebay_api.py          ← eBay Trading API integration
│   ├── quality_scorer.py    ← 0-100 listing quality score
│   └── database.py          ← SQLAlchemy + SQLite models
│
├── frontend/
│   ├── index.html           ← Main app (Single + Bulk mode)
│   ├── preview.html         ← Listing preview + editor
│   └── dashboard.html       ← Stats dashboard
│
├── config/
│   └── settings.py          ← Pydantic settings from .env
│
├── database/
│   └── listings.db          ← SQLite (auto-created)
│
├── static/
│   └── processed/           ← Downloaded + processed images
│
├── .env.example             ← Copy this to .env
├── requirements.txt
├── run.sh                   ← One-click start script
└── README.md
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/scrape` | Scrape a product URL |
| POST | `/api/generate/{id}` | Generate eBay listing |
| PATCH | `/api/listing/{id}` | Edit a listing |
| POST | `/api/publish/{id}` | Publish to eBay |
| POST | `/api/bulk` | Process multiple URLs |
| GET | `/api/listings` | Get all listings |
| GET | `/api/listing/{id}` | Get single listing |
| DELETE | `/api/listing/{id}` | Delete a listing |
| GET | `/api/dashboard` | Dashboard statistics |
| GET | `/api/ebay/verify` | Test eBay connection |

---

## Example Workflow

```
1. Open http://localhost:8000

2. Paste: https://www.amazon.com/dp/B0XXXXXXXX

3. Set markup to 80% (default)

4. Click "⚡ Generate Listing"
   → Scrapes Amazon for title, price, images, specs
   → Claude AI writes eBay-optimized title + description
   → Downloads + resizes all product images
   → Checks current eBay market prices
   → Shows quality score and profit estimate

5. Click "👁 Full Preview & Edit" to fine-tune anything

6. Click "🚀 Publish to eBay" to go live

7. View all listings at http://localhost:8000/dashboard
```

---

## Pricing Formula

```
eBay listing price = retail_price × (1 + markup)

Example:
  Retail price: $49.99
  Markup: 80%
  eBay price: $49.99 × 1.80 = $89.98

If eBay market average is $70.00:
  ⚠ Warning: Your price exceeds market average by 28%
  Suggested price: $66.50
```

---

## Shipping Calculation

```
If source site shows shipping estimate:
  eBay shipping = retail_shipping_days × 2

If no estimate found:
  eBay shipping = 10 business days (default)

+ Handling time: 2 days (configurable)
```

This protects you — you're dropshipping, so you need buffer time.

---

## Quality Score Breakdown

| Component | Max | Criteria |
|-----------|-----|----------|
| Title SEO | 25 | Length, keywords, brand, numbers |
| Description | 25 | Length, sections, bullet points |
| Images | 25 | Count (8+ = perfect score) |
| Price | 25 | Vs. eBay market average |

---

## Where To Improve From Here

The current version is a production-ready foundation. Here's what to build next:

### 🔥 High Impact

1. **eBay VeRO / Brand Risk Detection**
   - Query eBay's VeRO database before listing luxury brands
   - Prevent account suspension for restricted brands

2. **Arbitrage Scanner (the big one)**
   - Instead of manual URL pasting, auto-scan brand websites
   - Calculate retail vs eBay spread automatically
   - Surface profitable items without you looking

3. **Profit Tracking & Sales Data**
   - Connect eBay Selling API to track actual sales
   - Calculate real profit after eBay fees (13%) and shipping

4. **Image Background Removal**
   - Use remove.bg API or rembg library
   - White backgrounds dramatically improve eBay CTR

### 🧰 Technical Improvements

5. **Site-specific scrapers** — Amazon, Walmart, Target have unique HTML structures. Build dedicated scrapers for the 10 most common sources.

6. **Listing queue** — Background task queue (Celery/Redis) for bulk processing without blocking

7. **eBay fee calculator** — Auto-deduct 13.25% final value fee and $0.35 insertion fee from profit estimate

8. **Price history** — Track market prices over time to find the best listing window

9. **Duplicate detection** — Flag if you already have a similar item listed

10. **Auto-repricing** — Detect if a competitor drops price, auto-adjust yours

### 🎨 UX Improvements

11. **Drag-and-drop image reordering** — First image = thumbnail
12. **Description WYSIWYG editor** — Replace textarea with rich text editor
13. **Listing templates** — Save reusable description templates by category
14. **Mobile app** — React Native wrapper for on-the-go listing

---

## Troubleshooting

**Scraper returns empty data:**
- Some sites block scrapers. Try adding a delay or use a proxy.
- Check that Playwright browsers are installed: `playwright install chromium`

**eBay API errors:**
- Confirm `EBAY_ENVIRONMENT` matches your token (sandbox vs production)
- User tokens expire — refresh them in the eBay developer portal

**Images not loading:**
- Check `static/processed/` directory permissions
- Some retailers block hotlinking — images download instead

**Claude returns template output:**
- Verify `ANTHROPIC_API_KEY` is set in `.env`
- Check Anthropic console for API usage/limits

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| Scraping | Playwright (Chromium) |
| AI | Anthropic Claude (claude-sonnet-4) |
| Database | SQLite + SQLAlchemy (async) |
| Images | Pillow (PIL) |
| Frontend | Vanilla JS, CSS custom properties |
| HTTP client | HTTPX (async) |

---

## License

MIT — use it, fork it, sell it. Build your arbitrage empire.
