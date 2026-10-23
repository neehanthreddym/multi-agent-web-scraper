"""Check that the controlled product page is being served."""

from urllib.request import urlopen


with urlopen("http://127.0.0.1:8080/products/desk-lamp.html", timeout=3) as response:
    if response.status != 200:
        raise SystemExit(1)
