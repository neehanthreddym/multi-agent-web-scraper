"""Application-enforced limits for the first, owned-fixture-only flow."""

SOURCE_URL = "http://fixture:8080/products/desk-lamp.html"
# Server-owned exact destinations. Page content and clients cannot extend this list.
FIXTURE_PRESETS = (
    ("desk-lamp", "Studio Desk Lamp"),
    ("graph-monitor", "Focus Monitor · graph layout"),
    ("array-keyboard", "Quiet Keyboard · array layout"),
    ("multi-script-mouse", "Travel Mouse · multiple scripts"),
    ("missing-id-stand", "Adjustable Stand · missing ID"),
    ("missing-price-speaker", "Compact Speaker · missing price"),
    ("ambiguous-currency-mug", "Travel Mug · ambiguous currency"),
    ("invalid-price-hub", "USB Hub · invalid price"),
    ("multiple-offers-chair", "Task Chair · multiple offers"),
    ("missing-offer-shelf", "Wall Shelf · missing offer"),
)
FIXTURE_URLS = frozenset(
    f"http://fixture:8080/products/{preset_id}.html"
    for preset_id, _ in FIXTURE_PRESETS
)
PRODUCT_FIELDS = (
    "product_name", "source_product_id", "current_price",
    "currency", "availability", "product_url",
)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ATTEMPTS = 3
JOB_TIMEOUT_SECONDS = 600
LEASE_SECONDS = 90
