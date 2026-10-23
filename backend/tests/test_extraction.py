import json

import httpx
import pytest
from pydantic import ValidationError

from app.constants import MAX_RESPONSE_BYTES, PRODUCT_FIELDS, SOURCE_URL
from app.extraction import ExtractionError, extract_fields, fetch_page
from app.schemas import JobCreate


def page(product):
    return '<script type="application/ld+json">' + json.dumps(product) + '</script>'


@pytest.fixture
def product():
    return {
        "@type": "Product", "name": "Studio Desk Lamp", "sku": "LAMP-001",
        "offers": {"@type": "Offer", "price": "49.90", "priceCurrency": "USD",
                   "availability": "https://schema.org/InStock", "url": SOURCE_URL},
    }


def test_known_values_have_field_evidence(product):
    result = extract_fields(page(product), list(PRODUCT_FIELDS))
    assert {key: item["value"] for key, item in result.items()} == {
        "product_name": "Studio Desk Lamp", "source_product_id": "LAMP-001",
        "current_price": "49.90", "currency": "USD",
        "availability": "in_stock", "product_url": SOURCE_URL,
    }
    assert all(item["null_reason"] is None and item["evidence"] for item in result.values())
    assert result["current_price"]["evidence"]["field_path"] == "/offers/price"


def test_graph_and_single_offer_list_have_precise_evidence_path(product):
    product["offers"] = [product["offers"]]
    result = extract_fields(page({"@graph": [product]}), ["current_price"])
    assert result["current_price"]["value"] == "49.90"
    assert result["current_price"]["evidence"]["field_path"] == "/@graph/0/offers/0/price"


def test_missing_currency_remains_null_without_guessing(product):
    del product["offers"]["priceCurrency"]
    result = extract_fields(page(product), ["currency"])
    assert result["currency"]["value"] is None
    assert result["currency"]["null_reason"] == "missing_value"
    assert result["currency"]["evidence"] is None


@pytest.mark.parametrize("price", [True, "NaN", "Infinity", "-1", "1e100000", {"amount": 2}])
def test_invalid_prices_remain_null(product, price):
    product["offers"]["price"] = price
    result = extract_fields(page(product), ["current_price"])
    assert result["current_price"]["value"] is None
    assert result["current_price"]["null_reason"] == "unsupported_value"


def test_multiple_offers_are_not_arbitrarily_selected(product):
    product["offers"] = [product["offers"], {"price": "59.90"}]
    result = extract_fields(page(product), ["current_price"])
    assert result["current_price"]["value"] is None
    assert result["current_price"]["null_reason"] == "unsupported_offer_structure"


def test_multiple_products_require_investigation(product):
    with pytest.raises(ExtractionError, match="exactly one"):
        extract_fields(page([product, product]), ["product_name"])


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://169.254.169.254/", "https://example.com/",
    SOURCE_URL + "?next=http://example.com", "file:///etc/passwd",
])
def test_other_destinations_rejected_before_fetch(url):
    with pytest.raises(ValidationError):
        JobCreate(seed_url=url)
    with pytest.raises(ExtractionError, match="Destination"):
        fetch_page(url)


def mock_client(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(handler),
    ))


def test_redirects_are_not_followed(monkeypatch):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    mock_client(monkeypatch, handler)
    with pytest.raises(ExtractionError, match="Redirects"):
        fetch_page(SOURCE_URL)
    assert seen == [SOURCE_URL]


def test_response_size_is_bounded(monkeypatch):
    mock_client(monkeypatch, lambda request: httpx.Response(
        200, headers={"content-type": "text/html"}, content=b"x" * (MAX_RESPONSE_BYTES + 1),
    ))
    with pytest.raises(ExtractionError, match="2 MiB"):
        fetch_page(SOURCE_URL)


def test_configuration_rejects_extra_fields_and_duplicate_selections():
    with pytest.raises(ValidationError):
        JobCreate(selected_fields=["currency", "currency"])
    with pytest.raises(ValidationError):
        JobCreate(page_limit=2)
    with pytest.raises(ValidationError):
        JobCreate(allowed_domains=["example.com"])
