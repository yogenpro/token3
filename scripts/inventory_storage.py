"""Change-only full-inventory state/history; source responses are transient."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from .catalog_inventory import canonical, digest, normalize_inventory
from .provider_inventory import MAX_SOURCE_BYTES, PROVIDER_ID
from .inventory_retention import catalog_metadata, google_latest_time, google_pricing_observation, previous_catalog_semantics, semantic_record


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
    catalog, fingerprint = normalize_inventory(provider, body, result.source_kind, urls, observed_at)
    observation = google_pricing_observation(catalog)
    path = Path("provider_catalogs") / (provider + ".json")
    old_catalog = json.loads((data_dir / path).read_text()) if (data_dir / path).exists() else {}
    old_row = index.get(provider, {})
    revision = old_catalog.get("revision", 0)
    old_semantics = previous_catalog_semantics(old_catalog) if old_catalog else None
    latest = catalog.get("google_pricing_time_mode") == "latest"
    previous_latest = old_semantics is not None and old_semantics.get("google_pricing_time_mode") == "latest"
    previous_observed_at = old_catalog.get("google_pricing_observed_at", old_catalog.get("changed_at"))
    old_records = {r["id"]:r for r in old_catalog.get("records", [])}
    new_records = {r["id"]:r for r in catalog["records"]}
    record_changes = []
    for rid in sorted(old_records.keys() | new_records.keys()):
        previous, current = old_records.get(rid), new_records.get(rid)
        if previous == current:
            continue  # Clock aging alone must not invent a source-record change.
        comparable = bool(latest and previous_latest and previous_observed_at is not None and
                          google_latest_time(previous, previous_observed_at) and google_latest_time(current, observed_at))
        if semantic_record(previous, comparable, previous_observed_at) != semantic_record(current, comparable, observed_at):
            record_changes.append((rid, previous, current, comparable))
    changed = old_semantics is None or bool(record_changes) or catalog_metadata(old_semantics) != catalog_metadata(catalog)
    # Representation/provenance-policy changes refresh the current header, not
    # economic revisions or append-only history, including legacy fingerprints.
    rewrite = changed or old_catalog.get("catalog_sha256") != fingerprint
    events = []
    if changed:
        revision += 1
        for rid, previous, current, comparable in record_changes:
            kind = "record_added" if previous is None else "record_no_longer_listed" if current is None else "record_changed"
            # This is source-record absence, NOT an inferred model delisting.
            event_id = digest([provider, revision, kind, rid])[:32]
            event = dict(id=event_id, provider=provider, revision=revision, observed_at=observed_at,
                         catalog_sha256=fingerprint, kind=kind, record_id=rid, after=current)
            if comparable:
                # Both sides use the verified unbounded latest-price contract.
                event["google_pricing_time_mode"] = "latest"
            events.append(event)
        if catalog["billing_notes"] != old_catalog.get("billing_notes", []):
            events.append(dict(id=digest([provider, revision, "billing_notes"] )[:32], provider=provider, revision=revision,
                               observed_at=observed_at, catalog_sha256=fingerprint, kind="billing_notes_changed",
                               billing_notes=catalog["billing_notes"]))
    if rewrite:
        catalog.update(catalog_sha256=fingerprint, revision=revision, changed_at=observed_at if changed else old_catalog["changed_at"],
                       source_url=result.source_url, source_urls=urls, source_sha256=result.source_sha256,
                       archive_reference=None)
        if result.source_evidence:
            catalog["source_evidence"] = result.source_evidence
    else:
        catalog = None
    legacy = old_row.get("legacy_source_archive")
    if legacy is None and old_row.get("versions"):
        legacy = {key:old_row.get(key) for key in ("latest_path", "source_sha256", "versions", "version_count")}
    row = dict(id=provider, name=name, source_url=result.source_url, source_urls=urls, source_kind=result.source_kind,
               fallback_reason=result.fallback_reason, source_sha256=result.source_sha256,
               catalog_sha256=fingerprint, latest_path=path.as_posix(), record_count=len(old_catalog.get("records", [])) if catalog is None else len(catalog["records"]),
               revision=revision, first_seen_at=old_row.get("first_seen_at", observed_at), last_seen_at=observed_at,
               curated_parser_state="not_applicable" if result.inventory_only else "error" if result.parse_error else "ok",
               curated_parser_error=result.parse_error,
               collection_scope="inventory_only" if result.inventory_only else "inventory_and_reviewed_quotes",
               legacy_source_archive=legacy, archive_reference=old_row.get("archive_reference"))
    if result.source_evidence:
        row["source_evidence"] = result.source_evidence
    if observation is not None:
        row["google_pricing_observation"] = observation
    return row, catalog, events


def inventory_document(rows, observed_at):
    return dict(schema_version=2, updated_at=observed_at, provider_count=len(rows),
                scope="Full source-native model/meter/SKU/document pricing records. Native units, expressions, conditions and unknown values are preserved; these are not canonical cross-provider cost comparisons.",
                retention="Current normalized catalogs plus bounded immutable native-history segments and verified compact observations. Original migration history is archived losslessly. New raw responses are transient; pre-existing source archives are preserved unchanged.",
                providers=sorted(rows.values(), key=lambda row:row["id"]))


def history_content(path, events):
    before = path.read_text() if path.exists() else ""
    ids = {json.loads(line)["id"] for line in before.splitlines() if line}
    return before + "".join(canonical(e) + "\n" for e in events if e["id"] not in ids)
