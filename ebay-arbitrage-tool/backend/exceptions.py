class FlipForgeError(Exception):
    pass


class ScrapeError(FlipForgeError):
    pass


class BotBlockedError(ScrapeError):
    pass


class PriceUnavailableError(FlipForgeError):
    pass


class EbayAuthExpiredError(FlipForgeError):
    pass


class EbayAPIError(FlipForgeError):
    pass


class ImageDownloadError(FlipForgeError):
    pass
