"""Exact destination policy; no network or database is needed for these checks."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.constants import FIXTURE_PRESETS, FIXTURE_URLS, PRODUCT_FIELDS, SOURCE_URL
from app.extraction import ExtractionError, extract_fields, fetch_page
from app.main import app
from app.schemas import JobCreate


BAD_URLS = [
    "http://169.254.169.254/", "http://127.0.0.1/", "http://[::1]/",
    "https://example.com/product", "file:///etc/passwd",
    "http://fixture:8080/products/unknown.html", "http://fixture:8080/",
    SOURCE_URL + "?next=http://example.com", SOURCE_URL + "#fragment",
    SOURCE_URL.replace("http://", "https://"),
    SOURCE_URL.replace("fixture:8080", "fixture:80"),
    SOURCE_URL.replace("fixture:8080", "catalog@fixture:8080"),
    SOURCE_URL.replace("desk-lamp", "%64esk-lamp"),
    SOURCE_URL.replace("/products/", "/other/../products/"),
]


def test_presets_are_server_owned_and_keep_the_legacy_default():
    with TestClient(app) as client:
        response = client.get("/presets")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == len(FIXTURE_PRESETS) == 10
    assert len({item["id"] for item in items}) == 10
    assert {item["source_url"] for item in items} == FIXTURE_URLS
    assert items[0]["source_url"] == JobCreate().seed_url == SOURCE_URL


@pytest.mark.parametrize("url", sorted(FIXTURE_URLS))
def test_approved_urls_keep_one_page_and_canonical_field_order(url):
    config = JobCreate(seed_url=url, selected_fields=["currency", "product_name"])
    assert config.page_limit == 1
    assert config.selected_fields == ["product_name", "currency"]


@pytest.mark.parametrize("url", BAD_URLS)
def test_unknown_or_modified_destinations_reject_before_network_or_database(url, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A rejected destination reached the HTTP client")

    monkeypatch.setattr("app.extraction.httpx.Client", forbidden)
    with pytest.raises(ValidationError):
        JobCreate(seed_url=url)
    with pytest.raises(ExtractionError, match="Destination"):
        fetch_page(url)
    with TestClient(app) as client:
        response = client.post("/jobs", json={"seed_url": url}, headers={"Idempotency-Key": "invalid"})
    assert response.status_code == 422


def test_product_url_must_match_the_selected_page_not_another_approved_page():
    other_url = "http://fixture:8080/products/graph-monitor.html"
    product = {"@type": "Product", "offers": {"url": other_url}}
    html = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
    wrong_page = extract_fields(html, ["product_url"], source_url=SOURCE_URL)
    assert wrong_page["product_url"]["value"] is None
    assert wrong_page["product_url"]["null_reason"] == "unsupported_value"
    right_page = extract_fields(html, ["product_url"], source_url=other_url)
    assert right_page["product_url"]["value"] == other_url


def test_absent_and_explicit_null_offers_have_resolvable_evidence():
    for product in ({"@type": "Product"}, {"@type": "Product", "offers": None}):
        html = '<script type="application/ld+json">' + json.dumps(product) + '</script>'
        result = extract_fields(html, list(PRODUCT_FIELDS))
        citation = result["current_price"]["evidence"]
        assert result["current_price"]["null_reason"] == "missing_offer"
        if "offers" in product:
            assert citation["kind"] == "json_ld_value"
            assert citation["field_path"] == "/offers"
            assert json.loads(citation["excerpt"]) is None
        else:
            assert citation["kind"] == "json_ld_absence"
            assert citation["missing_key"] == "offers"
            assert json.loads(citation["excerpt"]) == product


def test_unsupported_single_offer_list_preserves_the_original_container():
    html = '<script type="application/ld+json">{"@type":"Product","offers":[null]}</script>'
    result = extract_fields(html, ["current_price"])["current_price"]
    assert result["null_reason"] == "unsupported_offer_structure"
    assert result["evidence"]["field_path"] == "/offers"
    assert json.loads(result["evidence"]["excerpt"]) == [None]
