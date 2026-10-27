"""Pure scoring for the one-product-per-page development dataset."""

from decimal import Decimal, InvalidOperation


SCORER_VERSION = "1.0.0"
NULL_REASONS = {
    "missing_value", "unsupported_value", "missing_offer", "unsupported_offer_structure",
}


def ratio(numerator: int, denominator: int) -> float | None:
    # No observations means undefined, not perfect accuracy.
    return numerator / denominator if denominator else None


def same_value(field: str, expected, predicted) -> bool:
    if expected is None or predicted is None:
        return expected is None and predicted is None
    if not isinstance(expected, str) or not isinstance(predicted, str):
        return False
    if field != "current_price":
        return expected == predicted
    try:
        left, right = Decimal(expected), Decimal(predicted)
        return left.is_finite() and right.is_finite() and left == right
    except InvalidOperation:
        return False


def field_rates(counts: dict) -> dict:
    tp, fp, fn = (counts[name] for name in ("tp", "fp", "fn"))
    return {
        **counts,
        "precision_denominator": tp + fp,
        "recall_denominator": tp + fn,
        "f1_denominator": 2 * tp + fp + fn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "f1": ratio(2 * tp, 2 * tp + fp + fn),
    }


def score_pages(pages: list[dict], selected_fields: list[str]) -> dict:
    """Match by page and slot; never match using a field being measured.

    Each page supplies expected/predicted records with a `fields` dictionary.
    The runner computes evidence_checks from saved bytes and authored labels.
    Extra slots are extra products; absent slots are missed products. The current
    dataset has exactly one expected slot per page, not a multi-product matcher.
    """
    if not selected_fields or len(set(selected_fields)) != len(selected_fields):
        raise ValueError("Select at least one unique field")
    counts = {name: {"tp": 0, "fp": 0, "fn": 0} for name in selected_fields}
    expected_count = predicted_count = matched_count = complete_count = exact_pages = 0
    null_total = null_values = null_reasons = spurious = missing_nulls = 0
    null_by_reason = {reason: {"total": 0, "correct_null_values": 0, "correct_null_reasons": 0,
                               "spurious_values": 0, "missing_predictions": 0}
                      for reason in sorted(NULL_REASONS)}
    non_null = cited = supported = review_count = 0
    findings = []

    def finding(page, index, kind, field=None):
        entry = {"page_id": page["page_id"], "record_index": index, "kind": kind}
        if field is not None:
            entry["field"] = field
        findings.append(entry)

    for page in pages:
        expected, predictions = page["expected"], page["predictions"]
        checks = page.get("evidence_checks", [])
        expected_count += len(expected)
        predicted_count += len(predictions)
        matched_count += min(len(expected), len(predictions))
        page_complete = len(expected) == len(predictions) and not page.get("failures")
        for index, prediction in enumerate(predictions):
            fields = prediction["fields"]
            review_count += any(fields.get(name, {}).get("value") is None for name in selected_fields)
            for name in selected_fields:
                observation = fields.get(name, {})
                if observation.get("value") is not None:
                    non_null += 1
                    has_evidence = isinstance(observation.get("evidence"), dict) and bool(observation["evidence"])
                    cited += has_evidence
                    gold = expected[index]["fields"][name] if index < len(expected) else None
                    checked = index < len(checks) and checks[index].get(name) is True
                    is_supported = bool(has_evidence and checked and gold is not None
                                        and same_value(name, gold["value"], observation["value"]))
                    supported += is_supported
                    if not is_supported:
                        finding(page, index, "unsupported_evidence", name)

        for index in range(max(len(expected), len(predictions))):
            gold_record = expected[index] if index < len(expected) else None
            prediction = predictions[index] if index < len(predictions) else None
            if gold_record is None:
                finding(page, index, "extra_product")
                for name in selected_fields:
                    counts[name]["fp"] += prediction["fields"].get(name, {}).get("value") is not None
                page_complete = False
                continue
            if prediction is None:
                finding(page, index, "missed_product")
            record_complete = prediction is not None
            for name in selected_fields:
                gold = gold_record["fields"][name]
                observed = prediction["fields"].get(name, {}) if prediction is not None else {}
                present = "value" in observed
                value = observed.get("value")
                value_matches = present and same_value(name, gold["value"], value)
                reason_matches = present and observed.get("null_reason") == gold["null_reason"]
                if gold["value"] is not None:
                    if value_matches:
                        counts[name]["tp"] += 1
                    else:
                        counts[name]["fn"] += 1
                        counts[name]["fp"] += value is not None
                else:
                    if gold["null_reason"] not in NULL_REASONS:
                        raise ValueError("Expected null label needs a supported reason")
                    null_total += 1
                    null_values += present and value is None
                    null_reasons += value_matches and reason_matches
                    spurious += value is not None
                    missing_nulls += not present
                    group = null_by_reason[gold["null_reason"]]
                    group["total"] += 1
                    group["correct_null_values"] += present and value is None
                    group["correct_null_reasons"] += value_matches and reason_matches
                    group["spurious_values"] += value is not None
                    group["missing_predictions"] += not present
                    counts[name]["fp"] += value is not None
                if not value_matches:
                    finding(page, index, "missing_field" if not present else "incorrect_value", name)
                elif not reason_matches:
                    finding(page, index, "incorrect_null_reason", name)
                record_complete = record_complete and value_matches and reason_matches
            complete_count += record_complete
            page_complete = page_complete and record_complete
        exact_pages += page_complete

    total = {key: sum(row[key] for row in counts.values()) for key in ("tp", "fp", "fn")}
    return {
        "matching_policy": "page_and_record_slot_single_product_v1",
        "field_metrics": {name: field_rates(row) for name, row in counts.items()},
        "micro": field_rates(total),
        "products": {
            "expected": expected_count, "predicted": predicted_count, "matched": matched_count,
            "missed": expected_count - matched_count, "extra": predicted_count - matched_count,
        },
        "complete_records": {
            "correct": complete_count, "total": expected_count,
            "accuracy": ratio(complete_count, expected_count),
        },
        "exact_pages": {"correct": exact_pages, "total": len(pages), "accuracy": ratio(exact_pages, len(pages))},
        "null_fields": {
            "total": null_total, "correct_null_values": null_values, "correct_null_reasons": null_reasons,
            "null_value_accuracy": ratio(null_values, null_total),
            "null_reason_accuracy": ratio(null_reasons, null_total),
            "spurious_values": spurious, "missing_predictions": missing_nulls,
            "by_expected_reason": {
                reason: {**row, "null_value_accuracy": ratio(row["correct_null_values"], row["total"]),
                         "null_reason_accuracy": ratio(row["correct_null_reasons"], row["total"])}
                for reason, row in null_by_reason.items()
            },
        },
        "evidence": {
            "non_null_predictions": non_null, "with_evidence": cited, "supported": supported,
            "coverage": ratio(cited, non_null), "correctness": ratio(supported, cited),
            "unsupported_values": non_null - supported,
            "unsupported_value_rate": ratio(non_null - supported, non_null),
            "correctness_scope": "agreement_with_authored_labels_and_saved_json_ld",
        },
        "review": {"needs_review": review_count, "predicted_records": predicted_count,
                   "rate": ratio(review_count, predicted_count)},
        "findings": findings,
    }
