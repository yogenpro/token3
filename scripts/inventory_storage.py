"""Change-only full-inventory state/history; source responses are transient."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from .catalog_inventory import canonical, digest, normalize_inventory
from .provider_inventory import MAX_SOURCE_BYTES, PROVIDER_ID


def prepare_catalog(provider, name, result, observed_at, data_dir, index):
    if not PROVIDER_ID.fullmatch(provider):
        raise ValueError("Invalid provider ID")
    body = result.source_payload
    if not isinstance(body, str) or not body:
        raise ValueError("Missing full source payload")
    if len(body.encode()) > MAX_SOURCE_BYTES or hashlib.sha256(body.encode()).hexdigest() != result.source_sha256:
        raise ValueError("Source payload size/hash validation failed")
    urls = result.source_urls or [result.source_url]
    if any(urlparse(url).scheme != "https" or not urlparse(url).hostname for url in urls + [result.source_url]):
        raise ValueError("Source URLs must be HTTPS")
    catalog, fingerprint = normalize_inventory(provider, body, result.source_kind)
    path = Path("provider_catalogs") / (provider + ".json")
    old_catalog = json.loads((data_dir / path).read_text()) if (data_dir / path).exists() else {}
    old_row = index.get(provider, {})
    revision = old_catalog.get("revision", 0)
    changed = old_catalog.get("catalog_sha256") != fingerprint
    events = []
    if changed:
        revision += 1
        old_records = {r["id"]:r for r in old_catalog.get("records", [])}
        new_records = {r["id"]:r for r in catalog["records"]}
        for rid in sorted(old_records.keys() | new_records.keys()):
            previous, current = old_records.get(rid), new_records.get(rid)
            if previous == current:
                continue
            kind = "record_added" if previous is None else "record_no_longer_listed" if current is None else "record_changed"
            # This is source-record absence, NOT an inferred model delisting.
            event_id = digest([provider, revision, kind, rid])[:32]
            events.append(dict(id=event_id, provider=provider, revision=revision, observed_at=observed_at,
                               catalog_sha256=fingerprint, kind=kind, record_id=rid, after=current))
        if catalog["billing_notes"] != old_catalog.get("billing_notes", []):
            events.append(dict(id=digest([provider, revision, "billing_notes"] )[:32], provider=provider, revision=revision,
                               observed_at=observed_at, catalog_sha256=fingerprint, kind="billing_notes_changed",
                               billing_notes=catalog["billing_notes"]))
        catalog.update(catalog_sha256=fingerprint, revision=revision, changed_at=observed_at,
                       source_url=result.source_url, source_urls=urls, source_sha256=result.source_sha256,
                       archive_reference=None)
    else:
        catalog = None
    legacy = old_row.get("legacy_source_archive")
    if legacy is None and old_row.get("versions"):
        legacy = {key:old_row.get(key) for key in ("latest_path", "source_sha256", "versions", "version_count")}
    row = dict(id=provider, name=name, source_url=result.source_url, source_urls=urls, source_kind=result.source_kind,
               fallback_reason=result.fallback_reason, source_sha256=result.source_sha256,
               catalog_sha256=fingerprint, latest_path=path.as_posix(), record_count=len(old_catalog.get("records", [])) if catalog is None else len(catalog["records"]),
               revision=revision, first_seen_at=old_row.get("first_seen_at", observed_at), last_seen_at=observed_at,
               curated_parser_state="error" if result.parse_error else "ok", curated_parser_error=result.parse_error,
               legacy_source_archive=legacy, archive_reference=old_row.get("archive_reference"))
    return row, catalog, events


def inventory_document(rows, observed_at):
    return dict(schema_version=2, updated_at=observed_at, provider_count=len(rows),
                scope="Full source-native model/meter/SKU/document pricing records. Native units, expressions, conditions and unknown values are preserved; these are not canonical cross-provider cost comparisons.",
                retention="Current normalized catalogs plus change-only JSONL history. New raw responses are transient; pre-existing source archives are preserved unchanged.",
                providers=sorted(rows.values(), key=lambda row:row["id"]))


def history_content(path, events):
    before = path.read_text() if path.exists() else ""
    ids = {json.loads(line)["id"] for line in before.splitlines() if line}
    return before + "".join(canonical(e) + "\n" for e in events if e["id"] not in ids)
