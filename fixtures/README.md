# Labeled catalog fixtures

This is the development dataset for Issue #3: ten owned static pages with an independently authored answer key. A fixture is a saved example page. A label is the expected value and the source evidence that supports it. These are development examples, not held-out accuracy data or model predictions.

The dataset is `catalog-development` version `1.0.0`, created on 2026-10-25. The existing desk-lamp HTML is included as the first example, unchanged; nine new pages bring the total to ten.

| Page ID | Case | Expected outcome |
|---|---|---|
| desk-lamp | Original single product and offer | valid |
| graph-monitor | Product in `@graph` after an unrelated node; out of stock | valid |
| array-keyboard | Top-level array; a one-element offers list; preorder | valid |
| multi-script-mouse | Second JSON-LD script; Product in an `@type` array | valid |
| missing-id-stand | No source SKU | needs_review |
| missing-price-speaker | Offer with no price | needs_review |
| ambiguous-currency-mug | `$` without an explicit currency code | needs_review |
| invalid-price-hub | Negative price | needs_review |
| multiple-offers-chair | Two offers with no primary offer | needs_review |
| missing-offer-shelf | Product with no offer | needs_review |

## Files and label contract

- `catalog/products/*.html`: the ten input pages. JSON-LD is inert data; there are no executable scripts or external assets in the new pages.
- `datasets/catalog-v1/manifest.json`: dataset metadata, selected fields, page IDs, paths, source URLs, SHA-256 hashes, coverage tags and expected outcomes.
- `datasets/catalog-v1/labels.json`: ten expected product identities and sixty field labels. Each label has a string value or null, a null reason, a rationale and an evidence reference.
- `verify_dataset.py`: standard-library-only consistency checks. It never imports the extractor, fetches pages, starts services, writes results or uses a model.

Manifest paths resolve relative to the manifest directory. `source_url` identifies the page within the fixture service; it does not grant permission to fetch it. Labels stay outside `catalog/`, which is the only served directory. The fixture Docker build excludes labels and the verifier. Later inference must receive only page bytes, never the answer key. Save future automated predictions separately, with dataset/extractor versions and hashes.

`dataset_product_id` is a stable dataset identity, not a fabricated source SKU. `source_product_id` remains null when the page omits it. Evidence identifies a zero-based JSON-LD `script_index` and an RFC 6901 `json_pointer`. Its `raw_value` and JSON-encoded `excerpt` must match the saved source. Absence evidence points to an existing parent object and names a missing key; it does not pretend that a missing field has a source value.

## Expected behavior and limits

Labels follow the `single_product_single_offer_v1` policy. Prices are decimal strings. Currency requires an explicit three-letter code; `$` is `null` with `unsupported_value`, never an assumed USD value. Availability uses `in_stock`, `out_of_stock`, or `preorder`. Missing fields use `missing_value`, and a missing offers object uses `missing_offer` for all offer-level fields.

Two offers are outside the one-offer scope: all four offer-level fields remain null with `unsupported_offer_structure`, with both offers retained in evidence. Names and SKUs are still labeled. Nulls do not remove a product from the expected count: every page contains one product. `valid` and `needs_review` are expected validation outcomes, not human approval decisions or observed job results.

These labels describe the intended deterministic behavior. Issue #4 adds ten exact server-owned presets to the API/worker and validates each extracted product URL against the selected page. User-run backend tests and the ten-fixture live acceptance check passed; direct browser review also passed on 2026-10-26. See the [verified checks in the architecture](../ARCHITECTURE.md#issue-4-implementation-and-verified-checks-2026-10-26). The labels, hashes and page bytes are unchanged. These are acceptance checks, not extraction scores; Issue #5 measures predictions against this dataset.

Treat released dataset bytes and labels as immutable. When changing either, create a new version and update hashes together; retain the old version so runs remain comparable. The baseline desk-lamp SHA-256 is `68141e6f81c7bf384bfcdf701e47d0a4bf305df04f276087f841e428c5457787`.

## User-run verification

From the repository root, using the existing local backend image:

```bash
podman compose run --rm --no-deps --volume "$PWD/fixtures:/dataset:ro" --workdir /dataset api python verify_dataset.py
```

This mounts saved files read-only and uses Python already in the image. It needs no database, broker, model, image rebuild or package installation. Alternatively, with host Python 3.12 available, run `python3 fixtures/verify_dataset.py` from the repository root.

Expected output (not a recorded test result):

```text
PASS catalog-development 1.0.0: 10 pages, 60 field labels, 60 evidence references
PASS hashes, coverage, identities, null reasons and evidence locators; 4 valid / 6 needs_review labels
PASS original desk-lamp bytes preserved; no extractor, network or model calls
```

Verified on 2026-10-25: the user supplied output from the Compose command above containing all three PASS lines exactly as shown. The output confirms ten pages, sixty field labels/evidence references, matching integrity/locator checks, and the preserved desk-lamp baseline. The Compose provider notice is informational; it was followed by successful container creation and verifier output.

The verifier checks structural integrity and source references, not extraction accuracy or the independent correctness of every label. Direct source review was performed separately. No ten-page extraction score is implied by this result.
