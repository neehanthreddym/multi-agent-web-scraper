"""User-run live acceptance check. Retains ten fixture jobs and one subset job."""

import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from app.constants import FIXTURE_URLS, MAX_ATTEMPTS
from app.smoke import check
from app.tasks import process_job


def main():
    directory = Path(os.environ.get("CATALOG_FIXTURES_ROOT", "/fixtures")) / "datasets/catalog-v1"
    manifest = json.loads((directory / "manifest.json").read_text())
    label_bytes = (directory / manifest["labels_file"]).read_bytes()
    check(hashlib.sha256(label_bytes).hexdigest() == manifest["labels_sha256"], "Labels hash mismatch")
    labels = {p["page_id"]: p for p in json.loads(label_bytes)["pages"]}
    run_key = "fixtures-" + uuid4().hex
    base = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8000")
    with httpx.Client(base_url=base, timeout=10, trust_env=False) as client:
        presets = client.get("/presets")
        presets.raise_for_status()
        check({p["source_url"] for p in presets.json()["items"]} == FIXTURE_URLS,
              "API preset set differs from the worker preset set")
        check({p["source_url"] for p in manifest["pages"]} == FIXTURE_URLS, "Dataset/preset mismatch")

        def submit(body, key):
            response = client.post("/jobs", json=body, headers={"Idempotency-Key": key})
            check(response.status_code == 202, f"Job creation returned {response.status_code}")
            return response.json()

        def read(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()

        def completed(job):
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                job = read("/jobs/" + job["id"])
                if job["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.5)
            check(job["status"] == "completed", f"Job {job['id']} ended as {job['status']}")
            check(1 <= job["attempts"] <= MAX_ATTEMPTS, "Attempt budget was exceeded")
            return job

        # Submit first, then wait within one global bound (not ten serial waits).
        pending = []
        for page in manifest["pages"]:
            key = run_key + "-" + page["page_id"]
            body = {"seed_url": page["source_url"]}
            job = submit(body, key)
            check(submit(body, key)["id"] == job["id"], "Submission was not idempotent")
            other = next(url for url in FIXTURE_URLS if url != page["source_url"])
            conflict = client.post("/jobs", json={"seed_url": other}, headers={"Idempotency-Key": key})
            check(conflict.status_code == 409, "Changed source reused an existing key")
            pending.append((page, job))

        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            statuses = [read("/jobs/" + job["id"])["status"] for _, job in pending]
            if all(status in {"completed", "failed", "cancelled"} for status in statuses):
                break
            time.sleep(1)
        check(all(status == "completed" for status in statuses), "Fixture jobs did not all complete: " + str(statuses))

        for page, original in pending:
            job = read("/jobs/" + original["id"])
            check(job["configuration"]["seed_url"] == page["source_url"], "Saved configuration changed")
            check(1 <= job["attempts"] <= MAX_ATTEMPTS, "Attempt budget exceeded")
            records = read("/jobs/" + job["id"] + "/records")["items"]
            check(len(records) == 1, "Expected exactly one original record")
            record = records[0]
            check(record["validation_status"] == page["expected_outcome"], "Unexpected validation status")
            expected = labels[page["page_id"]]["products"][0]["fields"]
            check(set(record["fields"]) == set(expected), "Saved field set differs")
            evidence = read("/records/" + record["id"] + "/evidence")
            check(evidence["source_url"] == page["source_url"] and evidence["observed_at"], "Missing provenance")
            check(evidence["fields"] == record["fields"], "Original evidence changed")
            snapshot = client.get(evidence["snapshot_text_path"])
            snapshot.raise_for_status()
            check(snapshot.headers["content-type"].startswith("text/plain"), "Unsafe snapshot content type")
            check(hashlib.sha256(snapshot.content).hexdigest() == evidence["sha256"] == page["sha256"],
                  "Saved snapshot differs from versioned fixture bytes")
            scripts = BeautifulSoup(snapshot.text, "lxml").select('script[type="application/ld+json"]')
            for name, field in record["fields"].items():
                check(field["value"] == expected[name]["value"] and field["null_reason"] == expected[name]["null_reason"],
                      page["page_id"] + ": unexpected field " + name)
                citation = field["evidence"]
                gold = expected[name]["evidence"][0]
                check(citation["script_index"] == gold["script_index"] and citation["field_path"] == gold["json_pointer"],
                      "Evidence locator differs from the labels")
                observed = json.loads(scripts[citation["script_index"]].get_text())
                for part in citation["field_path"].split("/")[1:]:
                    part = part.replace("~1", "/").replace("~0", "~")
                    observed = observed[int(part)] if isinstance(observed, list) else observed[part]
                check(citation["excerpt"] == json.dumps(observed, ensure_ascii=False)[:1000], "Evidence does not resolve")
                check(citation["kind"] == gold["kind"], "Evidence kind differs")
                if citation["kind"] == "json_ld_absence":
                    check(citation["missing_key"] == gold["missing_key"] and citation["missing_key"] not in observed,
                          "Incorrect absence evidence")
            # Re-enter the real worker function for a terminal job; it must be a no-op.
            process_job(job["id"])
            check(read("/jobs/" + job["id"] + "/records")["items"] == records, "Worker redelivery changed saved records")
            check(read("/jobs/" + job["id"])["attempts"] == job["attempts"], "Worker redelivery consumed another attempt")
            print("PASS fixture:", page["page_id"], "job:", job["id"])

        for body in (
            {"seed_url": "http://169.254.169.254/"},
            {"seed_url": manifest["pages"][0]["source_url"] + "?next=http://example.com"},
            {"seed_url": manifest["pages"][0]["source_url"], "page_limit": 2},
        ):
            response = client.post("/jobs", json=body, headers={"Idempotency-Key": run_key + "-rejected"})
            check(response.status_code == 422, "Unapproved source or page budget was accepted")

        subset = completed(submit({"seed_url": "http://fixture:8080/products/missing-offer-shelf.html",
                                   "selected_fields": ["product_name"]}, run_key + "-subset"))
        subset_records = read("/jobs/" + subset["id"] + "/records")["items"]
        check(len(subset_records) == 1 and set(subset_records[0]["fields"]) == {"product_name"}, "Subset selection changed")
        check(subset_records[0]["validation_status"] == "valid", "Validation ignored selected fields")
    print("PASS: ten live fixture jobs, selected fields, idempotency, terminal worker redelivery, rejection and saved evidence")
    print("No model calls or evaluation metrics; eleven jobs are retained for inspection.")


if __name__ == "__main__":
    main()
