"""
backend/quality_scorer.py
Evaluates a generated eBay listing quality from 0–100.

Scoring breakdown:
  Title    25 pts — keyword density, length, brand presence
  Description 25 pts — completeness, sections, bullet points
  Images   25 pts — count and resolution readiness
  Price    25 pts — competitiveness vs market
"""
import re
from typing import Dict, Optional


class QualityScorer:

    def score(
        self,
        title: str,
        description: str,
        image_count: int,
        price_check: Dict,
        brand: Optional[str] = None,
        specs: Optional[Dict] = None,
    ) -> Dict:
        title_score = self._score_title(title, brand)
        desc_score = self._score_description(description, specs)
        image_score = self._score_images(image_count)
        price_score = self._score_price(price_check)

        total = title_score + desc_score + image_score + price_score

        return {
            "total": total,
            "title_score": title_score,
            "description_score": desc_score,
            "image_score": image_score,
            "price_score": price_score,
            "breakdown": {
                "title": {
                    "score": title_score,
                    "max": 25,
                    "notes": self._title_notes(title, brand),
                },
                "description": {
                    "score": desc_score,
                    "max": 25,
                    "notes": self._desc_notes(description),
                },
                "images": {
                    "score": image_score,
                    "max": 25,
                    "notes": f"{image_count} image(s) found.",
                },
                "price": {
                    "score": price_score,
                    "max": 25,
                    "notes": price_check.get("message", ""),
                },
            },
        }

    def _score_title(self, title: str, brand: Optional[str]) -> int:
        score = 0
        if not title:
            return 0

        # Length: eBay titles should use most of the 80 chars
        length = len(title)
        if length >= 60:
            score += 10
        elif length >= 40:
            score += 7
        elif length >= 20:
            score += 4
        else:
            score += 1

        # Brand presence
        if brand and brand.lower() in title.lower():
            score += 5

        # Keyword density — no stop words taking up space
        words = title.split()
        meaningful_words = [
            w for w in words
            if w.lower() not in ("the", "a", "an", "and", "or", "for", "of", "in", "with")
        ]
        density = len(meaningful_words) / max(len(words), 1)
        if density > 0.7:
            score += 5
        elif density > 0.5:
            score += 3

        # Numbers/specs in title (size, model numbers) boost SEO
        if re.search(r"\d", title):
            score += 5

        return min(score, 25)

    def _score_description(self, description: str, specs: Optional[Dict]) -> int:
        if not description:
            return 0
        score = 0

        # Length
        length = len(description)
        if length > 800:
            score += 10
        elif length > 400:
            score += 7
        elif length > 100:
            score += 4

        # Has structured sections
        sections = ["overview", "feature", "specification", "shipping", "seller"]
        found = sum(1 for s in sections if s.lower() in description.lower())
        score += min(found * 2, 8)

        # Has bullet points / checkmarks
        if "✔" in description or "<li>" in description or "•" in description:
            score += 4

        # Has specs
        if specs and len(specs) > 2:
            score += 3

        return min(score, 25)

    def _score_images(self, image_count: int) -> int:
        if image_count >= 8:
            return 25
        elif image_count >= 5:
            return 20
        elif image_count >= 3:
            return 15
        elif image_count >= 1:
            return 8
        return 0

    def _score_price(self, price_check: Dict) -> int:
        if not price_check.get("market_avg"):
            # No market data — neutral score
            return 15
        if price_check.get("warning"):
            return 5
        # Competitive price
        your_price = price_check.get("your_price", 0)
        market_avg = price_check.get("market_avg", 0)
        if market_avg > 0:
            ratio = your_price / market_avg
            if ratio <= 0.9:
                return 25  # Priced below market — excellent
            elif ratio <= 1.0:
                return 22
            elif ratio <= 1.1:
                return 18
            elif ratio <= 1.2:
                return 12
            else:
                return 5
        return 15

    def _title_notes(self, title: str, brand: Optional[str]) -> str:
        issues = []
        if len(title) < 40:
            issues.append("Title is short — add more keywords")
        if brand and brand.lower() not in title.lower():
            issues.append("Brand not in title")
        if not re.search(r"\d", title):
            issues.append("No model number or size in title")
        return "; ".join(issues) if issues else "Title looks good"

    def _desc_notes(self, description: str) -> str:
        issues = []
        if len(description) < 200:
            issues.append("Description is short — add more detail")
        if "shipping" not in description.lower():
            issues.append("No shipping info in description")
        if "✔" not in description and "<li>" not in description:
            issues.append("Add bullet points for key features")
        return "; ".join(issues) if issues else "Description looks good"
