from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

DEMO_MODE = os.getenv('DEMO_MODE', 'true').lower() == 'true'
DEFAULT_MARKUP = float(os.getenv('DEFAULT_MARKUP', '0.8'))
DEFAULT_HANDLING = int(os.getenv('DEFAULT_HANDLING', '2'))
SHIPPING_MULTIPLIER = 2

DB_PATH = BASE_DIR / 'database' / 'listings.db'
IMAGE_DIR = BASE_DIR / 'static' / 'images'
PROCESSED_DIR = BASE_DIR / 'static' / 'processed'

EBAY_CLIENT_ID = os.getenv('EBAY_CLIENT_ID', '')
EBAY_CLIENT_SECRET = os.getenv('EBAY_CLIENT_SECRET', '')
EBAY_REDIRECT_URI = os.getenv('EBAY_REDIRECT_URI', 'http://localhost:8000/ebay/callback')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

EBAY_IMG_WIDTH = 1600
EBAY_IMG_HEIGHT = 1600
JPEG_QUALITY = 85
HTTP_TIMEOUT = 15.0
