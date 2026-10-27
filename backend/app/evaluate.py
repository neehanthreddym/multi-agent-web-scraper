"""Offline evaluation CLI. No database, broker, HTTP fetches or model inference."""

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import time
from importlib.metadata import version
from pathlib import Path

from bs4 import BeautifulSoup

from app.constants import FIXTURE_PRESETS, FIXTURE_URLS, MAX_RESPONSE_BYTES, PRODUCT_FIELDS
from app.evaluation_metrics import NULL_REASONS, SCORER_VERSION, same_value, score_pages
from app.extraction import extract_fields


REPORT_SCHEMA_VERSION = 1
METHOD_VERSION = "1.0.0"
INVALID_SCRIPT = object()


class DatasetError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DatasetError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def read_bounded(path: Path) -> bytes:
    with path.open("rb") as source:
        raw = source.read(MAX_RESPONSE_BYTES + 1)
    require(len(raw) <= MAX_RESPONSE_BYTES, f"Input exceeds 2 MiB: {path.name}")
    return raw


def parse_scripts(html: str) -> list:
    scripts = []
    for script in BeautifulSoup(html, "lxml").select('script[type="application/ld+json"]'):
        try:
            scripts.append(json.loads(script.get_text()))
        except (ValueError, RecursionError):
            # Keep indices aligned with the extractor even for invalid scripts.
            scripts.append(INVALID_SCRIPT)
    return scripts


def resolve_pointer(document, pointer: str):
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("Invalid JSON Pointer")
    for part in pointer[1:].split("/"):
        if re.search(r"~(?![01])", part):
            raise ValueError("Invalid JSON Pointer escape")
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(document, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", key):
                raise ValueError("Invalid array index")
            document = document[int(key)]
        elif isinstance(document, dict):
            document = document[key]
        else:
            raise ValueError("Pointer traverses a scalar")
    return document


def citation_value(scripts: list, citation: dict, pointer_key: str):
    index = citation["script_index"]
    if type(index) is not int or not 0 <= index < len(scripts) or scripts[index] is INVALID_SCRIPT:
        raise ValueError("Invalid script index")
    return resolve_pointer(scripts[index], citation[pointer_key])


def validate_label(field: str, label: dict, scripts: list):
    value, reason = label["value"], label["null_reason"]
    require((value is None and reason in NULL_REASONS)
            or (isinstance(value, str) and bool(value.strip()) and reason is None),
            f"Invalid value/null reason label: {field}")
    require(bool(label["rationale"]), f"Missing label rationale: {field}")
    require(value is None or same_value(field, value, value), f"Invalid normalized label: {field}")
    require(isinstance(label["evidence"], list) and bool(label["evidence"]), "Missing label evidence")
    for citation in label["evidence"]:
        raw = citation_value(scripts, citation, "json_pointer")
        require(canonical_bytes(raw) == canonical_bytes(citation["raw_value"]), "Label evidence does not resolve")
        require(canonical_bytes(json.loads(citation["excerpt"])) == canonical_bytes(raw), "Label excerpt differs")
        if citation["kind"] == "json_ld_absence":
            require(isinstance(raw, dict) and citation["missing_key"] not in raw, "Invalid absence evidence")
            require(value is None and reason in {"missing_value", "missing_offer"}, "Invalid absence label")
        else:
            require(citation["kind"] == "json_ld_value", "Unknown label evidence kind")


def load_dataset(fixtures_root: Path) -> tuple[dict, list[dict]]:
    root = fixtures_root.resolve()
    directory = (root / "datasets/catalog-v1").resolve()
    require(directory.is_relative_to(root), "Dataset directory escapes fixtures root")
    manifest_path = (directory / "manifest.json").resolve()
    require(manifest_path.parent == directory, "Manifest escapes the dataset directory")
    manifest_bytes = read_bounded(manifest_path)
    manifest = json.loads(manifest_bytes)
    label_path = (directory / manifest["labels_file"]).resolve()
    require(label_path.parent == directory, "Labels must stay in the dataset directory")
    label_bytes = read_bounded(label_path)
    require(sha256(label_bytes) == manifest["labels_sha256"], "Labels hash mismatch")
    labels = json.loads(label_bytes)
    for key in ("schema_version", "dataset_id", "dataset_version"):
        require(manifest[key] == labels[key], f"Dataset metadata differs: {key}")
    require(manifest["schema_version"] == 1 and manifest["dataset_version"] == "1.0.0", "Unsupported dataset version")
    require(manifest["split"] == "development", "Expected development split")
    require(labels["label_origin"] == "authored_ground_truth_not_extractor_output", "Expected authored labels")
    require(manifest["selected_fields"] == list(PRODUCT_FIELDS), "Expected all six fields in canonical order")
    pages, answers = manifest["pages"], labels["pages"]
    preset_ids = {identity for identity, _ in FIXTURE_PRESETS}
    require(len(pages) == len(answers) == len(preset_ids) == 10, "Expected ten labeled pages")
    require({p["page_id"] for p in pages} == {p["page_id"] for p in answers} == preset_ids, "Page identities differ")
    require({p["source_url"] for p in pages} == FIXTURE_URLS, "Dataset sources differ from server presets")
    by_id = {p["page_id"]: p for p in answers}
    loaded = []
    for page in sorted(pages, key=lambda item: item["page_id"]):
        path = (directory / page["path"]).resolve()
        require(path.parent == root / "catalog/products", "Page escapes catalog/products")
        require(path.name == page["page_id"] + ".html", "Page path differs from identity")
        require(page["source_url"] == f"http://fixture:8080/products/{path.name}", "Source/path mismatch")
        raw = read_bounded(path)
        require(sha256(raw) == page["sha256"], f"Page hash mismatch: {page['page_id']}")
        html = raw.decode("utf-8")
        scripts = parse_scripts(html)
        answer = by_id[page["page_id"]]
        require(answer["expected_product_count"] == len(answer["products"]) == 1, "Expected one product per page")
        product = answer["products"][0]
        require(product["dataset_product_id"] == page["page_id"] + "-product", "Incorrect label identity")
        require(set(product["fields"]) == set(PRODUCT_FIELDS), "Label field set differs")
        for field, label in product["fields"].items():
            validate_label(field, label, scripts)
        outcome = "needs_review" if any(f["value"] is None for f in product["fields"].values()) else "valid"
        require(page["expected_outcome"] == outcome, "Expected validation status differs from labels")
        loaded.append({"input": page, "html": html, "scripts": scripts, "expected": answer["products"]})
    baseline = manifest["preserved_baseline"]
    require(baseline["page_id"] == "desk-lamp", "Preserved baseline identity differs")
    require(next(p["input"]["sha256"] for p in loaded if p["input"]["page_id"] == "desk-lamp") == baseline["sha256"],
            "Preserved baseline hash differs")
    return {
        "id": manifest["dataset_id"], "version": manifest["dataset_version"], "split": manifest["split"],
        "label_origin": labels["label_origin"], "label_policy": manifest["label_policy"],
        "manifest_sha256": sha256(manifest_bytes), "labels_sha256": sha256(label_bytes),
        "selected_fields": list(PRODUCT_FIELDS),
    }, loaded


def evidence_matches(field: str, observation: dict, label: dict, scripts: list) -> bool:
    """Strict agreement with authored locators and saved bytes, not semantic inference."""
    citation = observation.get("evidence")
    if not isinstance(citation, dict) or not same_value(field, label["value"], observation.get("value")):
        return False
    try:
        raw = citation_value(scripts, citation, "field_path")
        if citation["excerpt"] != json.dumps(raw, ensure_ascii=False)[:1000]:
            return False
        for gold in label["evidence"]:
            matches = (citation["script_index"] == gold["script_index"]
                       and citation["field_path"] == gold["json_pointer"]
                       and citation["kind"] == gold["kind"]
                       and canonical_bytes(raw) == canonical_bytes(gold["raw_value"]))
            if matches and citation["kind"] == "json_ld_absence":
                matches = (isinstance(raw, dict) and citation.get("missing_key") == gold["missing_key"]
                           and gold["missing_key"] not in raw)
            if matches:
                return True
    except (KeyError, IndexError, ValueError, TypeError, OverflowError):
        pass
    return False


def run_evaluation(fixtures_root: Path, *, extractor=None) -> dict:
    started = time.perf_counter()
    dataset, loaded = load_dataset(fixtures_root)
    extractor = extract_fields if extractor is None else extractor
    pages = []
    for saved in loaded:
        page = saved["input"]
        predictions, failures, checks = [], [], []
        try:
            # The extractor sees only page bytes, selected fields and source URL.
            # Labels are used below for scoring, never supplied to extraction.
            fields = extractor(saved["html"], list(PRODUCT_FIELDS), source_url=page["source_url"])
            require(isinstance(fields, dict) and set(fields) == set(PRODUCT_FIELDS), "Extractor field set differs")
            require(all(isinstance(item, dict) and "value" in item and "null_reason" in item
                        for item in fields.values()), "Malformed extractor observations")
            predictions.append({"fields": fields, "validation_status": "valid" if all(
                f["value"] is not None for f in fields.values()) else "needs_review"})
        except Exception as error:
            failures.append({"type": type(error).__name__, "message": str(error)[:500]})
        if predictions:
            checks.append({field: evidence_matches(field, observation, saved["expected"][0]["fields"][field],
                                                  saved["scripts"])
                           for field, observation in predictions[0]["fields"].items()})
        pages.append({
            "page_id": page["page_id"], "source_url": page["source_url"], "input_path": page["path"],
            "input_sha256": page["sha256"], "expected": saved["expected"],
            "predictions": predictions, "evidence_checks": checks, "failures": failures,
        })
    directory = Path(__file__).resolve().parent
    hashes = {name: sha256((directory / name).read_bytes()) for name in (
        "extraction.py", "constants.py", "evaluation_metrics.py", "evaluate.py",
    )}
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "prediction_view": "automated_original",
        "dataset": dataset,
        "method": {"id": "json_ld_deterministic", "version": METHOD_VERSION,
                   "scorer_version": SCORER_VERSION, "source_sha256": hashes},
        "environment": {"python": platform.python_version(), "packages": {
            name: version(name) for name in ("beautifulsoup4", "lxml", "httpx")}},
        "metrics": score_pages(pages, list(PRODUCT_FIELDS)),
        "failures": [{"page_id": p["page_id"], **f} for p in pages for f in p["failures"]],
        "pages": pages,
    }
    # Timing varies. Inputs, versions, predictions, scores and failures form the
    # reproducible identity; runtime is deliberately outside that fingerprint.
    report["result_sha256"] = sha256(canonical_bytes(report))
    report["execution"] = {
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "extraction_attempts": len(pages), "retries": 0, "network_requests": 0, "model_calls": 0,
    }
    return report


def percentage(value) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def summary(report: dict) -> str:
    scores = report["metrics"]
    fields, records, nulls, evidence = (scores[key] for key in ("micro", "complete_records", "null_fields", "evidence"))
    return "\n".join([
        f"Offline evaluation: {report['dataset']['id']} {report['dataset']['version']}; {len(report['pages'])} pages",
        f"Fields: TP={fields['tp']} FP={fields['fp']} FN={fields['fn']}; "
        f"precision={percentage(fields['precision'])} recall={percentage(fields['recall'])} F1={percentage(fields['f1'])}",
        f"Complete records: {records['correct']}/{records['total']} ({percentage(records['accuracy'])})",
        f"Null reasons: {nulls['correct_null_reasons']}/{nulls['total']} ({percentage(nulls['null_reason_accuracy'])}); "
        f"spurious values={nulls['spurious_values']}",
        f"Evidence: coverage={percentage(evidence['coverage'])}; label/source agreement={percentage(evidence['correctness'])}; "
        f"unsupported={evidence['unsupported_values']}/{evidence['non_null_predictions']}",
        f"Extraction failures: {len(report['failures'])}; retries=0; HTTP requests=0; model calls=0",
        f"Result SHA-256: {report['result_sha256']}",
        f"Runtime: {report['execution']['elapsed_seconds']:.6f}s (excluded from result fingerprint)",
    ])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures-root", type=Path, default=Path(os.environ.get(
        "CATALOG_FIXTURES_ROOT", Path(__file__).resolve().parents[2] / "fixtures")))
    parser.add_argument("--check-repeat", action="store_true", help="Run twice and require identical result fingerprints")
    args = parser.parse_args(argv)
    try:
        report = run_evaluation(args.fixtures_root)
        if args.check_repeat:
            repeated = run_evaluation(args.fixtures_root)
            require(report["result_sha256"] == repeated["result_sha256"], "Repeated evaluation results differ")
            print("Repeatability: matching result SHA-256 across two runs", file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, IndexError, RecursionError) as error:
        print(f"Evaluation could not run: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
    print(summary(report), file=sys.stderr)
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
