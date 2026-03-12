# FlipForge — eBay Arbitrage Tool

> Paste any retail product URL → AI generates an optimised eBay listing in seconds.

![Tech Stack](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green) ![Playwright](https://img.shields.io/badge/Playwright-1.44-orange)

---

## What It Does

| Feature | Details |
|---|---|
| **URL Scraping** | Playwright-powered scraper handles JS-rendered pages (Amazon, Best Buy, Target, etc.) |
| **AI Listings** | Claude AI rewrites titles (eBay SEO, 80 char max) and descriptions |
| **Pricing Engine** | 80% markup + live eBay market price comparison |
| **Image Processing** | Downloads, resizes to 1600×1600 (eBay spec), optimises JPEG |
| **Shipping Calc** | Auto-doubles retail shipping time + adds handling |
| **Quality Score** | 0–100 score across title, description, images, price |
| **Bulk Mode** | Process up to 20 URLs at once |
| **eBay Publishing** | OAuth authentication + direct listing publish |
| **Dashboard** | Stats, profit tracking, listing management |

---

## Folder Structure

```
ebay-arbitrage-tool/
├── backend/
│   ├── main.py              ← FastAPI app, all API routes
│   ├── scraper.py           ← Playwright product scraper
│   ├── ebay_api.py          ← eBay OAuth + Inventory API
│   ├── pricing_engine.py    ← Price calc + eBay Browse API
│   ├── listing_generator.py ← Claude AI listing writer + quality score
│   ├── image_processor.py   ← Download + resize images
│   └── database.py          ← SQLAlchemy models, SQLite
├── frontend/
│   ├── index.html           ← Main UI (URL input, bulk mode)
│   ├── preview.html         ← Listing preview + editor
│   └── dashboard.html       ← Stats dashboard
├── config/
│   └── settings.py          ← All configuration
├── static/
│   ├── images/              ← Raw downloaded images
│   └── processed/           ← eBay-ready processed images
├── database/
│   └── listings.db          ← SQLite database (auto-created)
├── requirements.txt
├── .env.example
├── start.sh                 ← One-command setup + start
└── README.md
```

---

## Prerequisites

- Python 3.10 or higher
- pip
- Git (optional)

---

## Step-by-Step Installation

### 1. Download the project

```bash
# If you have git:
git clone <repo-url> ebay-arbitrage-tool
cd ebay-arbitrage-tool

# Or unzip the downloaded folder and open a terminal inside it.
```

### 2. Run the quick-start script

**macOS / Linux:**
```bash
chmod +x start.sh
./start.sh
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium --with-deps
copy .env.example .env
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open the app

Visit **http://localhost:8000** in your browser.

---

## API Credentials Setup

### eBay Developer Account

The tool uses two eBay APIs:
- **Browse API** — reads current market prices (free, no user login required)
- **Inventory API** — creates and publishes listings (requires user OAuth)

#### Steps:

1. Go to **https://developer.ebay.com** and sign in (or create a free account).

2. Click **"My Account"** → **"Application Keys"**.

3. Click **"Get a Free Key Set"** → Choose **Sandbox** (for testing) or **Production**.

4. You'll receive:
   - **App ID (Client ID)** → Copy this
   - **Cert ID (Client Secret)** → Copy this

5. Under **"User Tokens"** → **"Get an OAuth Token"** → add your redirect URI:
   ```
   http://localhost:8000/ebay/callback
   ```

6. Open your `.env` file and paste:
   ```
   EBAY_CLIENT_ID=your_app_id_here
   EBAY_CLIENT_SECRET=your_cert_id_here
   EBAY_ENV=sandbox
   ```

> 💡 **Start with Sandbox** — it's identical to production but doesn't create real listings. Switch to `EBAY_ENV=production` when ready to go live.

---

### Anthropic (Claude AI) — Optional

The AI listing writer dramatically improves title and description quality.

1. Go to **https://console.anthropic.com**
2. Sign up / sign in
3. Click **"API Keys"** → **"Create Key"**
4. Copy the key and add to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```

> Without this key, the tool uses a built-in rule-based generator. It still works — just less creative.

---

## Example Usage Workflow

### Workflow 1 — Single Product

1. Open **http://localhost:8000**
2. Paste a product URL, e.g.:
   ```
   https://www.amazon.com/dp/B08N5WRWNW
   ```
3. Adjust the **Markup slider** (default 80%)
4. Click **Generate Listing**
5. The tool will:
   - Launch headless Chromium and scrape the page
   - Download and process all product images
   - Generate an eBay-optimised title and description via Claude AI
   - Calculate your listing price
   - Check live eBay market prices
   - Show a ⚠️ warning if you're overpriced
6. Click **Preview** to see the full listing editor
7. Edit title, description, price, shipping as needed
8. Click **Publish to eBay** (requires eBay connection)

### Workflow 2 — Bulk Mode

1. Click the **Bulk Mode** tab
2. Paste multiple URLs (one per line):
   ```
   https://www.amazon.com/dp/B08N5WRWNW
   https://www.bestbuy.com/site/...
   https://www.target.com/p/...
   ```
3. Click **Generate Listings**
4. All listings are generated in sequence

### Workflow 3 — Connect eBay

1. Click **CONNECT EBAY** in the header
2. You'll be redirected to eBay's login page
3. Approve the permissions
4. You'll be redirected back with a green "✓ eBay Connected" badge
5. Now you can publish listings directly from the preview page

---

## Pricing Engine Logic

```
listing_price = retail_price × (1 + markup)
             = $100 × 1.80 = $180

If market_avg = $130:
  overage = (180 - 130) / 130 = 38%  > 20% threshold
  → ⚠ Warning shown
  → Suggested price = $130 × 0.97 = $126.10
```

---

## Quality Score Breakdown

| Dimension | Max Points | How it's calculated |
|---|---|---|
| Title | 30 | Word count, length, within 80 chars |
| Description | 25 | Length, keyword coverage |
| Images | 25 | Number of images (5 pts each) |
| Price | 20 | Distance from market average |
| **Total** | **100** | — |

---

## Where to Improve (Next Steps)

### High-Impact Improvements

1. **eBay Category Auto-Detection**
   - Use eBay's `findSuggestedCategories` API to automatically categorise listings
   - Currently listings need manual category assignment in eBay Seller Hub

2. **Background Job Queue**
   - Use Celery + Redis to process bulk listings asynchronously
   - Show real-time progress updates via WebSockets

3. **VeRO / Brand Risk Detection**
   - Check scraped brand names against eBay's Verified Rights Owner program list
   - Warn users before listing restricted brands (Gucci, Versace, etc.)

4. **Arbitrage Scanner**
   - Scheduled scraper that automatically scans luxury brand sites
   - Compares retail price vs eBay market price
   - Shows a ranked list of profitable arbitrage opportunities

5. **Image Background Removal**
   - Integrate `rembg` library to create clean white-background product photos
   - eBay favours clean product images in search rankings

6. **eBay Fees Calculator**
   - Factor in eBay's 13.25% final value fee
   - Show true profit after fees + shipping + PayPal

7. **Listing Performance Tracking**
   - Connect eBay Analytics API to pull views, watchers, sales data
   - Display conversion rate per listing in dashboard

8. **Multi-Marketplace Export**
   - Export listing data formatted for Amazon, Etsy, Facebook Marketplace

9. **Price History Chart**
   - Store daily eBay market prices per product
   - Show price trend charts on the preview page

10. **Browser Extension**
    - Chrome extension that adds a "Send to FlipForge" button on product pages

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `playwright install` fails | Run `playwright install-deps` first |
| Scraper returns empty data | Some sites block headless browsers. Try adding delays or rotating user agents. |
| eBay API 401 error | Token expired — click "Connect eBay" again to refresh |
| Images not loading | Check `static/processed/` folder permissions |
| `ModuleNotFoundError` | Make sure your venv is activated: `source .venv/bin/activate` |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI |
| Scraping | Playwright, BeautifulSoup4 |
| AI | Anthropic Claude claude-opus-4-5 |
| Database | SQLite + SQLAlchemy |
| Images | Pillow (PIL) |
| HTTP Client | httpx |
| Frontend | Vanilla JS, Tailwind CDN |
| Fonts | Google Fonts (Bebas Neue, DM Mono, DM Sans) |

---

## License

MIT — use freely, improve, and build your reselling empire. 🚀
