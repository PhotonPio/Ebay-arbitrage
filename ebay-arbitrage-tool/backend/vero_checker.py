VERO_HIGH_RISK = {
    "gucci", "louis vuitton", "chanel", "hermes", "rolex", "patek philippe",
    "audemars piguet", "cartier", "tiffany", "prada", "versace", "burberry",
    "supreme", "bape", "off-white", "balenciaga", "yeezy", "nike sb",
    "jordan", "apple", "sony playstation", "nintendo",
}
VERO_MEDIUM_RISK = {
    "omega", "tag heuer", "longines", "breitling", "ray-ban", "oakley",
    "michael kors", "coach", "kate spade", "ralph lauren", "tommy hilfiger",
}


def check_brand(brand: str) -> dict:
    b = (brand or "").strip().lower()
    if not b:
        return {"risk_level": "unknown", "reason": "No brand detected", "action_required": "Review manually."}
    if b in VERO_HIGH_RISK:
        return {"risk_level": "high", "reason": f"{brand} is frequently reported in VeRO", "action_required": "Only list authentic inventory with receipts."}
    if b in VERO_MEDIUM_RISK:
        return {"risk_level": "medium", "reason": f"{brand} may require authenticity proof", "action_required": "Keep invoices/serials ready before publishing."}
    return {"risk_level": "low", "reason": f"No major VeRO trend for {brand}", "action_required": "Proceed with normal compliance checks."}
