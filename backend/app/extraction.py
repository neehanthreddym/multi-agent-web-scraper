"""Bounded HTTP fetching and deterministic JSON-LD extraction. No model calls."""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.constants import FIXTURE_URLS, MAX_RESPONSE_BYTES, PRODUCT_FIELDS, SOURCE_URL


class ExtractionError(ValueError):
    pass


def fetch_page(url: str) -> bytes:
    # Exact server-owned fixtures are the only development-network exception.
    if url not in FIXTURE_URLS:
        raise ExtractionError("Destination is outside the owned fixture preset")
    with httpx.Client(timeout=30, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", url) as response:
            if response.is_redirect:
                raise ExtractionError("Redirects are unsupported in the fixture preset")
            response.raise_for_status()
            if "text/html" not in response.headers.get("content-type", "").lower():
                raise ExtractionError("Expected an HTML response")
            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise ExtractionError("Response exceeded the 2 MiB limit")
                body.extend(chunk)
            return bytes(body)


def products_in(value: Any, path: str = "") -> list[tuple[str, dict[str, Any]]]:
    if isinstance(value, list):
        return [product for index, item in enumerate(value)
                for product in products_in(item, f"{path}/{index}")]
    if not isinstance(value, dict):
        return []
    kind = value.get("@type")
    if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
        return [(path, value)]
    return products_in(value.get("@graph", []), path + "/@graph")


def extract_fields(
    html: str, selected_fields: list[str], *, source_url: str = SOURCE_URL,
) -> dict[str, dict[str, Any]]:
    if source_url not in FIXTURE_URLS:
        raise ExtractionError("Destination is outside the owned fixture presets")
    if not selected_fields or any(field not in PRODUCT_FIELDS for field in selected_fields):
        raise ExtractionError("Unsupported product fields")
    soup = BeautifulSoup(html, "lxml")
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for index, script in enumerate(soup.select('script[type="application/ld+json"]')):
        try:
            payload = json.loads(script.get_text())
        except (ValueError, RecursionError):
            continue
        candidates.extend((index, path, product) for path, product in products_in(payload))
    if len(candidates) != 1:
        raise ExtractionError("Expected exactly one unambiguous JSON-LD product")
    index, product_path, product = candidates[0]
    raw_offers = product.get("offers")
    offers = raw_offers
    offer_path = product_path + "/offers"
    if isinstance(offers, list) and len(offers) == 1:
        offers = offers[0]
        offer_path += "/0"
    offer_kind = offers.get("@type") if isinstance(offers, dict) else None
    offer = offers if isinstance(offers, dict) and offer_kind in (None, "Offer") else {}
    offer_reason = "missing_offer" if raw_offers is None else "unsupported_offer_structure"
    raw_fields = {
        "product_name": (product.get("name"), product_path + "/name"),
        "source_product_id": (product.get("sku"), product_path + "/sku"),
        "current_price": (offer.get("price"), offer_path + "/price"),
        "currency": (offer.get("priceCurrency"), offer_path + "/priceCurrency"),
        "availability": (offer.get("availability"), offer_path + "/availability"),
        "product_url": (offer.get("url"), offer_path + "/url"),
    }
    fields: dict[str, dict[str, Any]] = {}
    for field in selected_fields:
        raw, path = raw_fields[field]
        value: str | None = None
        reason: str | None = "missing_value"
        if field in {"current_price", "currency", "availability", "product_url"} and not offer:
            reason = offer_reason
        elif raw is not None:
            reason = "unsupported_value"
            if field in {"product_name", "source_product_id"}:
                if isinstance(raw, str) and 0 < len(raw.strip()) <= 500:
                    value = raw.strip()
            elif field == "current_price":
                if isinstance(raw, (str, int, float)) and not isinstance(raw, bool):
                    try:
                        price = Decimal(str(raw))
                        if price.is_finite() and 0 <= price <= Decimal("1000000000") and price.as_tuple().exponent >= -6:
                            value = format(price, "f")
                    except InvalidOperation:
                        pass
            elif field == "currency":
                if isinstance(raw, str) and re.fullmatch(r"[A-Z]{3}", raw):
                    value = raw
            elif field == "availability":
                value = {
                    "https://schema.org/InStock": "in_stock",
                    "https://schema.org/OutOfStock": "out_of_stock",
                    "https://schema.org/PreOrder": "preorder",
                }.get(raw) if isinstance(raw, str) else None
            elif field == "product_url" and isinstance(raw, str) and raw == source_url:
                value = raw
        if value is not None:
            reason = None
        citation = {
            "kind": "json_ld_value", "script_index": index,
            "field_path": path, "excerpt": json.dumps(raw, ensure_ascii=False)[:1000],
        } if raw is not None else None
        if field in {"current_price", "currency", "availability", "product_url"} and not offer:
            absent_offer = "offers" not in product
            citation = {
                "kind": "json_ld_absence" if absent_offer else "json_ld_value",
                "script_index": index,
                "field_path": product_path if absent_offer else product_path + "/offers",
                "excerpt": json.dumps(product if absent_offer else raw_offers, ensure_ascii=False)[:1000],
            }
            if absent_offer:
                citation["missing_key"] = "offers"
        elif raw is None:
            # An explicit JSON null is different evidence from an absent key.
            parent = offer if field in {"current_price", "currency", "availability", "product_url"} else product
            parent_path, key = path.rsplit("/", 1)
            citation = {
                "kind": "json_ld_value" if key in parent else "json_ld_absence",
                "script_index": index,
                "field_path": path if key in parent else parent_path,
                "excerpt": json.dumps(None if key in parent else parent, ensure_ascii=False)[:1000],
            }
            if key not in parent:
                citation["missing_key"] = key
        fields[field] = {
            "value": value,
            "null_reason": reason,
            "extraction_method": "json_ld",
            "evidence": citation,
        }
    return fields
