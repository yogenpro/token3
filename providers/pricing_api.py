"""Credential-safe helpers for official pricing/catalog APIs (no inference calls)."""
import json
from urllib.parse import urlencode

from .common import fetch_text

MAX_CATALOG_BYTES = 40 * 1024 * 1024


def encode_payload(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def fetch_pages(base_url, item_key, headers, token_keys=("nextPageToken",), max_pages=100):
    """Assemble complete pages, retaining all non-item metadata and source URLs.

    Pagination accepts opaque tokens, never arbitrary server-supplied URLs. A
    incomplete/cyclic/oversized listing raises before any snapshot is applied.
    """
    items, metadata, urls, seen = [], [], [], set()
    url, size = base_url, 0
    for _ in range(max_pages):
        body = fetch_text(url, headers=headers)
        size += len(body.encode("utf-8"))
        if size > MAX_CATALOG_BYTES:
            raise ValueError("Pricing API listing exceeds the 40 MiB collection limit")
        page = json.loads(body)
        if not isinstance(page, dict) or not isinstance(page.get(item_key), list):
            raise ValueError("Pricing API page is missing its {} list".format(item_key))
        if any(not isinstance(item, dict) for item in page[item_key]):
            raise ValueError("Pricing API items must be objects")
        items.extend(page[item_key])
        metadata.append({key: value for key, value in page.items() if key != item_key})
        urls.append(url)
        tokens = [page.get(key) for key in token_keys if page.get(key) not in (None, "")]
        if not tokens:
            if not items:
                raise ValueError("Pricing API returned an empty catalog")
            return {item_key: items, "page_count": len(urls), "page_metadata": metadata}, urls
        token = tokens[0]
        if not isinstance(token, str) or any(value != token for value in tokens):
            raise ValueError("Invalid or conflicting pricing API page tokens")
        if token in seen:
            raise ValueError("Pricing API pagination repeated a token")
        seen.add(token)
        url = base_url + ("&" if "?" in base_url else "?") + urlencode({"pageToken": token})
    raise ValueError("Pricing API pagination exceeded {} pages".format(max_pages))
