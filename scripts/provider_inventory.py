"""Store immutable, complete provider pricing-source snapshots separately from curated rows."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

MAX_SOURCE_BYTES = 50 * 1024 * 1024
PROVIDER_ID = re.compile(r"[a-z0-9-]+\Z")


class _HTMLTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table_depth = 0
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.table_depth == 0:
                self.rows = []
            self.table_depth += 1
        elif self.table_depth and tag == "tr":
            self.row = []
        elif self.table_depth and tag in ("th", "td") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.table_depth:
            self.table_depth -= 1
            if self.table_depth == 0 and self.rows:
                self.tables.append(self.rows)


def _markdown_tables(body):
    tables, current, header = [], [], None
    def flush():
        nonlocal current, header
        if header is not None:
            tables.append({"headers": header, "rows": current})
        current, header = [], None
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            flush()
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if header is None:
            header = cells
        elif len(cells) == len(header):
            current.append(cells)
        else:
            flush()
    flush()
    return tables


def _json_record_count(payload):
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return None
    if isinstance(payload.get("cloud_billing_catalog"), dict):
        return _json_record_count(payload["cloud_billing_catalog"].get("catalog"))
    for key in ("Items", "data", "models", "skus", "services"):
        if isinstance(payload.get(key), list):
            return len(payload[key])
    products = sum(len(value.get("products", {})) for value in payload.values() if isinstance(value, dict))
    return products or None


def _payload_format(body):
    stripped = body.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            def reject_constant(value):
                raise ValueError("Invalid JSON number: {}".format(value))
            payload = json.loads(body, parse_constant=reject_constant)
            tables = []
            document = payload.get("curated_pricing_document") if isinstance(payload, dict) else None
            if isinstance(document, dict) and isinstance(document.get("body"), str):
                _, _, tables = _payload_format(document["body"])
            return "json", payload, tables
        except (json.JSONDecodeError, ValueError):
            pass
    if stripped[:256].lower().startswith(("<!doctype html", "<html")) or "<table" in stripped[:4096].lower():
        tables = []
        try:
            parser = _HTMLTables()
            parser.feed(body)
            tables = [{"headers": rows[0], "rows": rows[1:]} for rows in parser.tables if rows]
        except Exception:
            pass  # The complete HTML remains preserved verbatim.
        return "html", body, tables
    tables = _markdown_tables(body)
    if stripped.startswith(("#", "|")) or tables:
        return "markdown", body, tables
    return "text", body, []


def prepare_source(provider, provider_name, result, observed_at, data_dir, index):
    """Return a new index row and an immutable source artifact (if needed)."""
    if not PROVIDER_ID.fullmatch(provider):
        raise ValueError("Invalid provider ID for source inventory")
    body = result.source_payload
    if not isinstance(body, str) or not body:
        raise ValueError("Collector did not retain its complete source payload")
    encoded = body.encode("utf-8")
    if len(encoded) > MAX_SOURCE_BYTES:
        raise ValueError("Provider source payload exceeds the 50 MiB archive limit")
    digest = hashlib.sha256(encoded).hexdigest()
    if digest != result.source_sha256:
        raise ValueError("Provider source payload does not match its SHA-256")
    source_urls = getattr(result, "source_urls", None) or [result.source_url]
    for source_url in [result.source_url] + source_urls:
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("Provider source inventory requires HTTPS source URLs")

    parse_error = getattr(result, "parse_error", None)
    source_kind = getattr(result, "source_kind", None) or "documentation"
    fallback_reason = getattr(result, "fallback_reason", None)
    payload_format, payload, tables = _payload_format(body)
    old = index.get(provider, {})
    versions = [dict(version) for version in old.get("versions", [])]
    version = next((row for row in versions if row.get("source_sha256") == digest), None)
    relative = Path("provider_sources") / provider / (digest + ".json")
    artifact_path = data_dir / relative
    artifact = None
    rebuild = version is None or not artifact_path.exists()
    if version is None:
        version = {
            "source_sha256": digest,
            "path": relative.as_posix(),
            "first_observed_at": observed_at,
            "last_seen_at": observed_at,
        }
        versions.append(version)
    else:
        version["last_seen_at"] = observed_at
        # Upgrade extraction metadata without altering the hashed source body.
        if not rebuild:
            try:
                rebuild = json.loads(artifact_path.read_text(encoding="utf-8")).get("schema_version") != 5
            except (OSError, json.JSONDecodeError):
                rebuild = True
    if rebuild:
        artifact = {
            "schema_version": 5,
            "provider_id": provider,
            "provider_name": provider_name,
            "source_url": result.source_url,
            "source_urls": source_urls,
            "source_kind": source_kind,
            "source_sha256": digest,
            "first_observed_at": version.get("first_observed_at", observed_at),
            "payload_format": payload_format,
            "payload_bytes": len(encoded),
            "source_body": body if payload_format == "json" else None,
            "table_count": len(tables),
            "table_row_count": sum(len(table["rows"]) for table in tables),
            "payload_record_count": _json_record_count(payload) if payload_format == "json" else sum(len(table["rows"]) for table in tables),
            "tables": tables,
            "payload": payload,
        }

    row = {
        "id": provider,
        "name": provider_name,
        "source_url": result.source_url,
        "source_urls": source_urls,
        "source_kind": source_kind,
        "fallback_reason": fallback_reason,
        "source_sha256": digest,
        "latest_path": relative.as_posix(),
        "payload_format": payload_format,
        "payload_bytes": len(encoded),
        "table_count": len(tables),
        "table_row_count": sum(len(table["rows"]) for table in tables),
        "payload_record_count": _json_record_count(payload) if payload_format == "json" else sum(len(table["rows"]) for table in tables),
        "first_seen_at": min((v["first_observed_at"] for v in versions), default=observed_at),
        "last_seen_at": observed_at,
        "version_count": len(versions),
        "curated_parser_state": "error" if parse_error else "ok",
        "curated_parser_error": parse_error,
        "versions": versions,
    }
    return row, artifact


def inventory_document(provider_rows, observed_at):
    return {
        "schema_version": 1,
        "updated_at": observed_at,
        "scope": "Uncurated official pricing/catalog source snapshots for all integrated providers. Payloads preserve each source's own model IDs, modalities, price dimensions, units, tiers, and regions; they are not normalized or published in the dashboard.",
        "provider_count": len(provider_rows),
        "providers": sorted(provider_rows.values(), key=lambda row: row["id"]),
    }
