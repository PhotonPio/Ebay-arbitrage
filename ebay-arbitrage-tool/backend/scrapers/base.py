from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class BaseScraper:
    source_url: str

    def supports(self) -> bool:
        return True


class EbayScraper(BaseScraper):
    def supports(self) -> bool:
        return "ebay." in urlparse(self.source_url).netloc.lower()


class AmazonScraper(BaseScraper):
    def supports(self) -> bool:
        return "amazon." in urlparse(self.source_url).netloc.lower()


class WalmartScraper(BaseScraper):
    def supports(self) -> bool:
        return "walmart." in urlparse(self.source_url).netloc.lower()
