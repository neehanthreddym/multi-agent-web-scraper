"""Check saved dataset integrity without running extraction or using the network."""

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "datasets" / "catalog-v1"
FIELDS = {
    "product_name", "source_product_id", "current_price",
    "currency", "availability", "product_url",
}
NULL_REASONS = {"missing_value", "unsupported_value", "missing_offer", "unsupported_offer_structure"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class SavedPage(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=False)
        self.scripts = []
        self.buffer = None
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self.buffer = []
        elif tag == "script":
            raise ValueError("Fixture contains an executable script")
        require(not any(key.startswith("on") for key in attributes), "Inline event handler")
        require(tag not in {"iframe", "object", "embed"}, "Executable embedded content")

    def handle_data(self, data):
        if self.buffer is not None:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.buffer is not None:
            self.scripts.append(json.loads("".join(self.buffer)))
            self.buffer = None


def resolve(document, pointer):
    if pointer == "":
        return document
    require(pointer.startswith("/"), "Invalid JSON Pointer")
    for part in pointer[1:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


def check_dataset():
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    label_path = (DATASET / manifest["labels_file"]).resolve()
    require(label_path.parent == DATASET, "Labels must stay in the dataset directory")
    label_bytes = label_path.read_bytes()
    require(sha256(label_bytes) == manifest["labels_sha256"], "Labels hash mismatch")
    labels = json.loads(label_bytes)
    for key in ("schema_version", "dataset_id", "dataset_version"):
        require(manifest[key] == labels[key], f"Metadata mismatch: {key}")
    require(manifest["schema_version"] == 1, "Unsupported schema version")
    require(manifest["dataset_version"] == "1.0.0", "Unexpected catalog-v1 version")
    require(manifest["split"] == "development", "Development data must be labeled explicitly")
    require(set(manifest["selected_fields"]) == FIELDS, "Incorrect selected fields")
    require(len(manifest["selected_fields"]) == len(FIELDS), "Duplicate selected fields")
    require(labels["label_origin"] == "authored_ground_truth_not_extractor_output", "Incorrect label origin")
    pages = manifest["pages"]
    require(len(pages) == len(labels["pages"]) == 10, "Expected exactly ten pages")
    ids = [page["page_id"] for page in pages]
    label_ids = [page["page_id"] for page in labels["pages"]]
    require(len(set(ids)) == len(set(label_ids)) == 10, "Duplicate page identities")
    require(set(ids) == set(label_ids), "Manifest/label identities differ")
    require(len({page["path"] for page in pages}) == 10, "Duplicate page paths")
    require(len({page["source_url"] for page in pages}) == 10, "Duplicate source URLs")
    coverage = {tag for page in pages for tag in page["coverage"]}
    require({"ordinary", "missing_fields", "ambiguous_currency", "invalid_prices", "multiple_offers",
             "graph", "top_level_array", "multiple_scripts", "single_offer_list", "type_array"} <= coverage,
            "Required scenarios or layouts are missing")
    by_id = {page["page_id"]: page for page in labels["pages"]}
    field_count = evidence_count = review_count = 0
    for page in pages:
        path = (DATASET / page["path"]).resolve()
        require(path.parent == ROOT / "catalog" / "products", "Page escapes catalog/products")
        require(path.suffix == ".html", "Expected an HTML page")
        require(page["source_url"] == f"http://fixture:8080/products/{path.name}", "Incorrect source URL")
        raw = path.read_bytes()
        require(sha256(raw) == page["sha256"], f"Page hash mismatch: {path.name}")
        saved = SavedPage(raw.decode("utf-8"))
        require(saved.scripts, f"No JSON-LD in {path.name}")
        answer = by_id[page["page_id"]]
        require(answer["expected_product_count"] == len(answer["products"]) == 1, "Expected one product")
        record = answer["products"][0]
        require(record["dataset_product_id"] == page["page_id"] + "-product", "Incorrect product identity")
        require(set(record["fields"]) == FIELDS, "Missing or extra field labels")
        has_null = False
        for field, label in record["fields"].items():
            field_count += 1
            value, reason = label["value"], label["null_reason"]
            require(label["rationale"], "Every label needs a rationale")
            if value is None:
                has_null = True
                require(reason in NULL_REASONS, f"Invalid null reason: {field}")
            else:
                require(isinstance(value, str) and value.strip() and reason is None, f"Invalid value: {field}")
            require(label["evidence"], f"Missing evidence: {field}")
            for evidence in label["evidence"]:
                evidence_count += 1
                index = evidence["script_index"]
                require(type(index) is int and 0 <= index < len(saved.scripts), "Invalid script index")
                observed = resolve(saved.scripts[index], evidence["json_pointer"])
                require(observed == evidence["raw_value"], f"Evidence mismatch: {path.name}:{field}")
                require(json.loads(evidence["excerpt"]) == observed, "Excerpt does not match source")
                if evidence["kind"] == "json_ld_absence":
                    require(isinstance(observed, dict) and evidence["missing_key"] not in observed,
                            "Absence evidence points to a present key")
                    require(value is None and reason in {"missing_value", "missing_offer"}, "Invalid absence label")
                else:
                    require(evidence["kind"] == "json_ld_value", "Unknown evidence kind")
        outcome = "needs_review" if has_null else "valid"
        require(page["expected_outcome"] == outcome, "Outcome disagrees with labels")
        review_count += has_null
    baseline = manifest["preserved_baseline"]
    require(baseline["page_id"] == "desk-lamp", "Original fixture identity changed")
    require(sha256((ROOT / "catalog/products/desk-lamp.html").read_bytes()) == baseline["sha256"],
            "Original desk-lamp bytes changed")
    require(field_count == evidence_count == 60, "Expected sixty field labels and evidence references")
    print(f"PASS catalog-development 1.0.0: 10 pages, {field_count} field labels, {evidence_count} evidence references")
    print(f"PASS hashes, coverage, identities, null reasons and evidence locators; {10 - review_count} valid / {review_count} needs_review labels")
    print("PASS original desk-lamp bytes preserved; no extractor, network or model calls")


if __name__ == "__main__":
    check_dataset()
