"""User-run live backend smoke check. Creates and retains one uniquely keyed job."""

import hashlib
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from bs4 import BeautifulSoup

from app.constants import SOURCE_URL


BASE = "http://127.0.0.1:8000"


def request(path, data=None, key=None):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Idempotency-Key"] = key
    payload = None if data is None else json.dumps(data).encode()
    with urlopen(Request(BASE + path, data=payload, headers=headers), timeout=10) as response:
        return json.load(response)


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    key = "smoke-" + str(uuid4())
    body = {"seed_url": SOURCE_URL}
    job = request("/jobs", body, key)
    check(request("/jobs", body, key)["id"] == job["id"], "Idempotent submission created another job")
    try:
        request("/jobs", {**body, "selected_fields": ["currency"]}, key)
    except HTTPError as error:
        check(error.code == 409, "Unexpected status for idempotency conflict")
    else:
        raise RuntimeError("A reused key accepted a different configuration")
    try:
        request("/jobs", {"seed_url": "http://169.254.169.254/"}, "rejected-" + key)
    except HTTPError as error:
        check(error.code == 422, "Unexpected status for rejected destination")
    else:
        raise RuntimeError("An unapproved destination was accepted")

    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        job = request("/jobs/" + job["id"])
        if job["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(1)
    check(job["status"] == "completed", "Job did not complete: " + json.dumps(job))
    records = request("/jobs/" + job["id"] + "/records")["items"]
    check(len(records) == 1, "Expected exactly one saved record")
    record = records[0]
    expected = {
        "product_name": "Studio Desk Lamp", "source_product_id": "LAMP-001",
        "current_price": "49.90", "currency": "USD", "availability": "in_stock",
        "product_url": SOURCE_URL,
    }
    check({name: field["value"] for name, field in record["fields"].items()} == expected,
          "Unexpected extracted values")
    evidence = request("/records/" + record["id"] + "/evidence")
    check(all(field["evidence"] for field in evidence["fields"].values()), "Missing field evidence")
    with urlopen(BASE + evidence["snapshot_text_path"], timeout=10) as response:
        check(response.headers.get_content_type() == "text/plain", "Snapshot was not served as text")
        snapshot = response.read()
    check(hashlib.sha256(snapshot).hexdigest() == evidence["sha256"], "Snapshot hash mismatch")
    scripts = BeautifulSoup(snapshot.decode("utf-8"), "lxml").select('script[type="application/ld+json"]')
    for field in evidence["fields"].values():
        citation = field["evidence"]
        value = json.loads(scripts[citation["script_index"]].get_text())
        for part in citation["field_path"].split("/")[1:]:
            value = value[int(part)] if isinstance(value, list) else value[part]
        check(json.dumps(value, ensure_ascii=False)[:1000] == citation["excerpt"],
              "Field evidence did not resolve against the saved page")
    print("PASS: live API -> outbox -> RabbitMQ -> worker -> PostgreSQL record and evidence")
    print("PASS: idempotent submission, rejected destination, snapshot integrity and safe content type")
    print("Saved job:", job["id"])
    print("Saved record:", record["id"])


if __name__ == "__main__":
    main()
