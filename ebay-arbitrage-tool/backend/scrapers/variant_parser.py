import json
import re
from itertools import product

from bs4 import BeautifulSoup


def extract_variants(soup: BeautifulSoup) -> list[dict]:
    groups: dict[str, set[str]] = {}

    for select in soup.select("select"):
        name = select.get("aria-label") or select.get("name") or select.get("id") or "Option"
        values = {
            opt.get_text(" ", strip=True)
            for opt in select.select("option")
            if opt.get_text(" ", strip=True)
        }
        values = {v for v in values if v.lower() not in {"select", "choose", "choose an option"}}
        if len(values) > 1:
            groups.setdefault(name, set()).update(values)

    for el in soup.select("[data-color],[data-size],[data-variant],[data-option]"):
        label = (
            el.get("data-variant")
            or el.get("data-option")
            or ("Color" if el.get("data-color") else "Size" if el.get("data-size") else "Option")
        )
        value = el.get("data-color") or el.get("data-size") or el.get("aria-label") or el.get_text(" ", strip=True)
        if value and len(value) < 60:
            groups.setdefault(label, set()).add(value)

    for script in soup.find_all("script"):
        raw = script.string or script.get_text() or ""
        if not raw or ("variant" not in raw.lower() and "option" not in raw.lower()):
            continue
        for match in re.findall(r'"(?:color|size|name)"\s*:\s*"([^"]{1,50})"', raw, re.I):
            if any(ch.isdigit() for ch in match) and len(match) > 5:
                continue
            label = "Size" if re.search(r"\b(?:xs|s|m|l|xl|xxl|\d{1,2}(?:\.5)?)\b", match, re.I) else "Color"
            groups.setdefault(label, set()).add(match)
        if script.get("type") == "application/json":
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict) and isinstance(payload.get("variants"), list):
                    for item in payload["variants"]:
                        if isinstance(item, dict):
                            for k in ("color", "size"):
                                if item.get(k):
                                    groups.setdefault(k.capitalize(), set()).add(str(item[k]))
            except Exception:
                pass

    return [
        {"name": name, "options": sorted(vals)}
        for name, vals in groups.items()
        if len(vals) > 1
    ]


def flatten_variants(variant_groups: list[dict]) -> list[dict]:
    if not variant_groups:
        return []
    keys = [group["name"] for group in variant_groups]
    options = [group.get("options", []) for group in variant_groups]
    return [dict(zip(keys, combo)) for combo in product(*options) if all(combo)]
