"""Metric edge cases and the offline report contract; no live services."""

import copy
import hashlib
import json
import os
import shutil
import socket
from pathlib import Path

import pytest

from app import evaluate
from app.constants import PRODUCT_FIELDS
from app.evaluation_metrics import same_value, score_pages
from app.extraction import ExtractionError, extract_fields


def observation(value, reason=None, evidence=None):
    return {"value": value, "null_reason": reason, "evidence": evidence}


def record(**fields):
    return {"fields": fields}


def scored(expected, predictions, fields=("currency",), checks=()):
    return score_pages([{"page_id": "example", "expected": expected, "predictions": predictions,
                         "evidence_checks": list(checks)}], list(fields))


def test_wrong_non_null_value_is_both_false_positive_and_false_negative():
    result = scored([record(currency=observation("USD"))], [record(currency=observation("EUR"))])
    assert {key: result["micro"][key] for key in ("tp", "fp", "fn")} == {"tp": 0, "fp": 1, "fn": 1}
    assert result["micro"]["precision_denominator"] == result["micro"]["recall_denominator"] == 1
    assert result["micro"]["f1"] == 0
    assert result["complete_records"]["accuracy"] == 0


def test_missing_value_and_spurious_value_on_a_null_label_have_separate_counts():
    expected = record(currency=observation("USD"), current_price=observation(None, "missing_value"))
    predicted = record(currency=observation(None, "missing_value"), current_price=observation("9.00"))
    result = scored([expected], [predicted], fields=("currency", "current_price"))
    assert result["field_metrics"]["currency"]["fn"] == 1
    assert result["field_metrics"]["current_price"]["fp"] == 1
    assert result["null_fields"]["spurious_values"] == 1
    assert result["null_fields"]["null_reason_accuracy"] == 0


def test_correct_null_with_wrong_reason_does_not_make_a_complete_record():
    result = scored([record(currency=observation(None, "missing_value"))],
                    [record(currency=observation(None, "unsupported_value"))])
    assert result["null_fields"]["correct_null_values"] == 1
    assert result["null_fields"]["correct_null_reasons"] == 0
    assert result["null_fields"]["by_expected_reason"]["missing_value"]["total"] == 1
    assert result["null_fields"]["by_expected_reason"]["missing_offer"]["total"] == 0
    assert result["complete_records"]["correct"] == 0
    assert result["micro"]["precision"] is None
    assert result["micro"]["recall"] is None
    assert result["micro"]["f1"] is None


def test_missing_field_is_not_a_correct_null():
    result = scored([record(currency=observation(None, "missing_offer"))], [record()])
    assert result["null_fields"]["missing_predictions"] == 1
    assert result["null_fields"]["correct_null_values"] == 0
    assert result["complete_records"]["accuracy"] == 0


def test_missed_product_fails_even_if_every_expected_field_is_null():
    result = scored([record(currency=observation(None, "missing_offer"))], [])
    assert result["products"]["missed"] == 1
    assert result["complete_records"] == {"correct": 0, "total": 1, "accuracy": 0}
    assert result["null_fields"]["null_reason_accuracy"] == 0


def test_missed_non_null_product_stays_in_recall_denominator():
    result = scored([record(currency=observation("USD"))], [])
    assert result["micro"]["fn"] == result["micro"]["recall_denominator"] == 1
    assert result["micro"]["precision"] is None
    assert result["micro"]["recall"] == result["micro"]["f1"] == 0


def test_duplicate_product_adds_false_positives_and_fails_exact_page_accuracy():
    product = record(currency=observation("USD", evidence={"script_index": 0}))
    result = scored([product], [product, copy.deepcopy(product)], checks=({"currency": True}, {"currency": True}))
    assert result["products"]["extra"] == 1
    assert result["micro"]["tp"] == result["micro"]["fp"] == 1
    assert result["micro"]["precision"] == 0.5
    assert result["micro"]["recall"] == 1
    assert result["micro"]["f1"] == pytest.approx(2 / 3)
    assert result["complete_records"]["accuracy"] == 1  # Expected-record denominator.
    assert result["exact_pages"]["accuracy"] == 0       # Extras are explicitly penalized here.
    assert result["evidence"]["supported"] == 1         # Extra records have no gold support.


def test_empty_denominators_are_undefined_not_perfect_scores():
    result = score_pages([], ["currency"])
    assert result["micro"]["f1"] is None
    assert result["complete_records"]["accuracy"] is None
    assert result["evidence"]["coverage"] is None
    assert result["null_fields"]["null_reason_accuracy"] is None


@pytest.mark.parametrize("citation,checked", [(None, True), ({"invalid": True}, False)])
def test_evidence_presence_is_distinct_from_support(citation, checked):
    expected = record(currency=observation("USD"))
    predicted = record(currency=observation("USD", evidence=citation))
    result = scored([expected], [predicted], checks=({"currency": checked},))
    assert result["evidence"]["coverage"] == (0 if citation is None else 1)
    assert result["evidence"]["supported"] == 0
    assert result["evidence"]["unsupported_value_rate"] == 1


def test_correct_locator_cannot_support_a_wrong_prediction():
    result = scored([record(currency=observation("USD"))],
                    [record(currency=observation("EUR", evidence={"script_index": 0}))],
                    checks=({"currency": True},))
    assert result["evidence"]["coverage"] == 1
    assert result["evidence"]["correctness"] == 0


@pytest.mark.parametrize("value,expected", [("49.9", True), ("49.900", True), ("49.91", False),
                                           ("NaN", False), ("Infinity", False), (True, False), (49.9, False)])
def test_price_equivalence_uses_finite_decimal_strings(value, expected):
    assert same_value("current_price", "49.90", value) is expected


def test_other_fields_are_exact_and_do_not_guess_currency():
    assert not same_value("currency", "USD", "$")
    assert not same_value("product_name", "Desk Lamp", "desk lamp")


def test_json_pointer_handles_escapes_and_rejects_invalid_array_indices():
    source = {"a/b": {"~key": ["first", "second"]}}
    assert evaluate.resolve_pointer(source, "/a~1b/~0key/1") == "second"
    for pointer in ("/a~1b/~0key/-1", "/a~1b/~0key/01", "/a~2b"):
        with pytest.raises(ValueError):
            evaluate.resolve_pointer(source, pointer)


@pytest.fixture
def fixture_root():
    path = Path(os.environ.get("CATALOG_FIXTURES_ROOT", Path(__file__).resolve().parents[2] / "fixtures"))
    if not (path / "datasets/catalog-v1/manifest.json").is_file():
        pytest.fail("Mount the repository fixtures directory at /fixtures:ro")
    return path


@pytest.fixture
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline evaluation attempted network access or HTTP fetching")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr("app.extraction.fetch_page", forbidden)


def test_ten_page_report_is_reproducible_and_keeps_original_predictions(fixture_root, offline):
    first = evaluate.run_evaluation(fixture_root)
    second = evaluate.run_evaluation(fixture_root)
    assert first["result_sha256"] == second["result_sha256"]
    stable = {key: value for key, value in first.items() if key not in {"execution", "result_sha256"}}
    independent_hash = hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False,
                                                allow_nan=False, separators=(",", ":")).encode()).hexdigest()
    assert first["result_sha256"] == independent_hash
    assert len(first["pages"]) == first["metrics"]["products"]["expected"] == 10
    assert not first["failures"]
    assert first["prediction_view"] == "automated_original"
    assert first["metrics"]["complete_records"]["correct"] == 10
    assert sum(len(p["predictions"][0]["fields"]) for p in first["pages"]) == 60
    assert set(first["method"]["source_sha256"]) == {
        "extraction.py", "constants.py", "evaluation_metrics.py", "evaluate.py",
    }
    for page in first["pages"]:
        assert all(page["evidence_checks"][0].values())
        assert len(page["input_sha256"]) == 64
    assert first["execution"]["model_calls"] == first["execution"]["network_requests"] == 0
    assert first["execution"]["retries"] == 0


def test_extraction_failure_is_retained_and_scored_as_a_missed_product(fixture_root, offline, monkeypatch, capsys):
    def partly_failing(html, fields, *, source_url):
        if source_url.endswith("/graph-monitor.html"):
            raise ExtractionError("Deliberate extraction failure")
        return extract_fields(html, fields, source_url=source_url)

    report = evaluate.run_evaluation(fixture_root, extractor=partly_failing)
    assert report["failures"] == [{"page_id": "graph-monitor", "type": "ExtractionError",
                                   "message": "Deliberate extraction failure"}]
    assert report["metrics"]["products"]["missed"] == 1
    assert report["metrics"]["micro"]["fn"] == 6
    assert report["metrics"]["complete_records"]["total"] == 10
    assert report["metrics"]["complete_records"]["correct"] == 9
    monkeypatch.setattr(evaluate, "extract_fields", partly_failing)
    assert evaluate.main(["--fixtures-root", str(fixture_root)]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["failures"] == report["failures"]
    assert "Extraction failures: 1" in output.err


def test_evidence_check_rejects_wrong_locators_excerpts_and_false_absence(fixture_root, offline):
    _, pages = evaluate.load_dataset(fixture_root)
    shelf = next(p for p in pages if p["input"]["page_id"] == "missing-offer-shelf")
    fields = extract_fields(shelf["html"], list(PRODUCT_FIELDS), source_url=shelf["input"]["source_url"])
    label = shelf["expected"][0]["fields"]["current_price"]
    for key, value in (("script_index", True), ("field_path", "/missing"),
                       ("excerpt", "made up"), ("missing_key", "name")):
        altered = copy.deepcopy(fields["current_price"])
        altered["evidence"][key] = value
        assert not evaluate.evidence_matches("current_price", altered, label, shelf["scripts"])


def test_cli_separates_json_from_summary_and_checks_repeatability(fixture_root, offline, capsys):
    assert evaluate.main(["--fixtures-root", str(fixture_root), "--check-repeat"]) == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert "Repeatability: matching result SHA-256" in output.err
    assert "Offline evaluation:" in output.err
    assert report["result_sha256"] in output.err
    assert str(fixture_root.resolve()) not in output.out


@pytest.fixture
def copied_fixtures(fixture_root, tmp_path):
    return Path(shutil.copytree(fixture_root, tmp_path / "fixtures"))


def test_changed_page_bytes_abort_before_extraction(copied_fixtures):
    path = copied_fixtures / "catalog/products/desk-lamp.html"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(evaluate.DatasetError, match="Page hash mismatch"):
        evaluate.run_evaluation(copied_fixtures, extractor=lambda *args, **kwargs: pytest.fail("Must not extract"))


def test_label_hash_mismatch_returns_no_scored_report(copied_fixtures, capsys):
    path = copied_fixtures / "datasets/catalog-v1/labels.json"
    path.write_bytes(path.read_bytes() + b"\n")
    assert evaluate.main(["--fixtures-root", str(copied_fixtures)]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert "Labels hash mismatch" in output.err


def test_manifest_cannot_read_labels_outside_its_directory(copied_fixtures):
    path = copied_fixtures / "datasets/catalog-v1/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["labels_file"] = "../outside.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(evaluate.DatasetError, match="Labels must stay"):
        evaluate.load_dataset(copied_fixtures)


def test_rehashed_but_invalid_gold_evidence_is_rejected(copied_fixtures):
    directory = copied_fixtures / "datasets/catalog-v1"
    labels_path, manifest_path = directory / "labels.json", directory / "manifest.json"
    labels = json.loads(labels_path.read_text())
    labels["pages"][0]["products"][0]["fields"]["currency"]["evidence"][0]["raw_value"] = "EUR"
    label_bytes = json.dumps(labels).encode()
    labels_path.write_bytes(label_bytes)
    manifest = json.loads(manifest_path.read_text())
    manifest["labels_sha256"] = hashlib.sha256(label_bytes).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(evaluate.DatasetError, match="Label evidence does not resolve"):
        evaluate.load_dataset(copied_fixtures)


def test_page_path_cannot_escape_catalog_products(copied_fixtures):
    path = copied_fixtures / "datasets/catalog-v1/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["pages"][0]["path"] = "../../../outside.html"
    path.write_text(json.dumps(manifest))
    with pytest.raises(evaluate.DatasetError, match="Page escapes"):
        evaluate.load_dataset(copied_fixtures)


def test_oversized_input_is_rejected(tmp_path):
    path = tmp_path / "oversized.html"
    path.write_bytes(b"x" * (evaluate.MAX_RESPONSE_BYTES + 1))
    with pytest.raises(evaluate.DatasetError, match="Input exceeds 2 MiB"):
        evaluate.read_bounded(path)


def test_repeatability_failure_publishes_no_json(monkeypatch, capsys):
    results = iter([{"result_sha256": "first"}, {"result_sha256": "different"}])
    monkeypatch.setattr(evaluate, "run_evaluation", lambda root: next(results))
    assert evaluate.main(["--check-repeat"]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert "Repeated evaluation results differ" in output.err
