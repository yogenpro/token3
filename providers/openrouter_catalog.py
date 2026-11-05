"""Availability authority for the exact, unfiltered public OpenRouter list."""

SOURCE = "https://openrouter.ai/api/v1/models"


def complete_model_ids(catalog, source):
    # The official list is unpaginated when offset/limit are omitted. Filtered,
    # authenticated and individual-model sources have no absence authority here.
    if source != SOURCE or not isinstance(catalog, dict):
        raise ValueError("OpenRouter availability requires the unfiltered public catalog")
    rows, total, links = catalog.get("data"), catalog.get("total_count"), catalog.get("links")
    if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("OpenRouter catalog must be a nonempty object list")
    if isinstance(total, bool) or not isinstance(total, int) or total != len(rows):
        raise ValueError("OpenRouter availability requires an exact integer catalog total")
    if not isinstance(links, dict) or "next" not in links or links["next"] is not None:
        raise ValueError("OpenRouter availability requires an explicit final-page marker")
    if any(catalog.get(key) for key in ("has_more", "hasMore", "next", "nextPageToken", "next_page_token")):
        raise ValueError("OpenRouter catalog has unresolved pagination")
    ids = set()
    for row in rows:
        mid = row.get("id")
        if not isinstance(mid, str) or not mid or mid in ids:
            raise ValueError("OpenRouter catalog has a missing or duplicate model ID")
        if row.get("private") or row.get("is_private") or row.get("is_public") is False or row.get("visibility") == "private":
            raise ValueError("OpenRouter availability requires public model records")
        ids.add(mid)
    return ids
