"""Application-enforced limits for the first, owned-fixture-only flow."""

SOURCE_URL = "http://fixture:8080/products/desk-lamp.html"
PRODUCT_FIELDS = (
    "product_name", "source_product_id", "current_price",
    "currency", "availability", "product_url",
)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ATTEMPTS = 3
JOB_TIMEOUT_SECONDS = 600
LEASE_SECONDS = 90
