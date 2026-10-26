"""Acceptance examples from the saved dataset; not an accuracy-scoring runner."""

import hashlib
import json
import os
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup

from app.constants import FIXTURE_PRESETS, FIXTURE_URLS, PRODUCT_FIELDS
from app.extraction import ExtractionError, extract_fields, fetch_page


@pytest.fixture(scope="module")
def dataset():
    root = Path(os.environ.get("CATALOG_FIXTURES_ROOT", Path(__file__).resolve().parents[2] / "fixtures"))
    directory = root / "datasets/catalog-v1"
    if not directory.is_dir():
        pytest.fail("Mount the repository fixtures directory at /fixtures:ro before running backend tests")
    manifest = json.loads((directory / "manifest.json").read_text())
    labels_bytes = (directory / manifest["labels_file"]).read_bytes()
    assert hashlib.sha256(labels_bytes).hexdigest() == manifest["labels_sha256"]
    labels = json.loads(labels_bytes)
    assert {page["source_url"] for page in manifest["pages"]} == FIXTURE_URLS
    assert len(manifest["pages"]) == len(labels["pages"]) == 10
    return directory, {p["page_id"]: p for p in manifest["pages"]}, {
        p["page_id"]: p for p in labels["pages"]
    }


@pytest.mark.parametrize("preset_id", [identity for identity, _ in FIXTURE_PRESETS])
def test_saved_fixture_fields_and_evidence_match_labels(preset_id, dataset, monkeypatch):
    directory, pages, labels = dataset
    page = pages[preset_id]
    raw = (directory / page["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == page["sha256"]
    seen = []

    def respond(request):
        seen.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "text/html"}, content=raw)

    original = httpx.Client
    monkeypatch.setattr("app.extraction.httpx.Client", lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(respond),
    ))
    fetched = fetch_page(page["source_url"])
    assert fetched == raw
    assert seen == [page["source_url"]]
    result = extract_fields(fetched.decode("utf-8"), list(PRODUCT_FIELDS), source_url=page["source_url"])
    expected = labels[preset_id]["products"][0]["fields"]
    scripts = BeautifulSoup(raw.decode("utf-8"), "lxml").select('script[type="application/ld+json"]')
    assert set(result) == set(expected)
    for name, field in result.items():
        assert field["value"] == expected[name]["value"], (preset_id, name)
        assert field["null_reason"] == expected[name]["null_reason"], (preset_id, name)
        assert field["extraction_method"] == "json_ld"
        citation = field["evidence"]
        gold = expected[name]["evidence"][0]
        assert citation["script_index"] == gold["script_index"]
        assert citation["field_path"] == gold["json_pointer"]
        assert citation["kind"] == gold["kind"]
        observed = json.loads(scripts[citation["script_index"]].get_text())
        for part in citation["field_path"].split("/")[1:]:
            key = part.replace("~1", "/").replace("~0", "~")
            observed = observed[int(key)] if isinstance(observed, list) else observed[key]
        assert observed == gold["raw_value"]
        assert citation["excerpt"] == json.dumps(observed, ensure_ascii=False)[:1000]
        if citation["kind"] == "json_ld_absence":
            assert citation["missing_key"] == gold["missing_key"]
            assert citation["missing_key"] not in observed
    status = "valid" if all(f["value"] is not None for f in result.values()) else "needs_review"
    assert status == page["expected_outcome"]


@pytest.mark.parametrize("url", sorted(FIXTURE_URLS))
def test_approved_page_redirects_are_still_rejected(url, monkeypatch):
    seen = []

    def respond(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    original = httpx.Client
    monkeypatch.setattr("app.extraction.httpx.Client", lambda **kwargs: original(
        **kwargs, transport=httpx.MockTransport(respond),
    ))
    with pytest.raises(ExtractionError, match="Redirects"):
        fetch_page(url)
    assert seen == [url]
