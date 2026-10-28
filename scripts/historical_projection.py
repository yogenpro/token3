"""Read-only, explicitly whitelisted historical evidence for the static dashboard.

The verified warehouse stays private to the build. No raw bytes, transport
receipts, disk paths, arbitrary model metadata or reviewed prices are emitted.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .historical_ledger import read_snapshot

MODEL_FIELDS = set("id model_name name display_name title type reported_type description pricing max_tokens context_length context_size context_window quantization deprecated deprecated_at replaced_by expiration_date status available architecture top_provider input_limits per_request_limits input_token_price_per_m output_token_price_per_m regions modalities version supported_parameters reasoning_options".split())
SCOPE_FIELDS = set("service sku term_type offer_id region regions flavor source_url identity_basis headings upstream_provider page".split())
REQUEST_FIELDS = set("service region version version_scope profile final_url target_url archive byte_start byte_length storage_url retrieval_url".split())
FORBIDDEN = {"authorization", "api_key", "apikey", "access_token", "refresh_token", "password", "secret", "credentials"}


def public_url(value):
    p = urlsplit(value)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password or any(
            any(word in key.lower() for word in ("key", "token", "secret", "signature", "credential", "authorization"))
            for key, _ in parse_qsl(p.query) if key.lower() not in {"pagetoken", "page_token", "$skiptoken"}):
        raise ValueError("Unsafe historical public URL")
    return value


def safe_value(value):
    if isinstance(value, dict):
        if any(k.lower().replace("-", "_") in FORBIDDEN for k in value):
            raise ValueError("Credential field in selected public historical evidence")
        return {k: safe_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_value(v) for v in value]
    if isinstance(value, str) and value.startswith(("https://", "http://")) and not any(c.isspace() for c in value):
        public_url(value)
    return value


def pick(value, keys):
    return safe_value({k: v for k, v in value.items() if k in keys})


def cells(values):
    return [pick(c, {"text", "code"}) for c in values]


def project_assertion(row):
    source, kind = row["source_record"], row["assertion_type"]
    if kind == "aws_sku_dimension":
        evidence = dict(product=pick(source["product"], {"sku", "productFamily", "attributes"}),
                        term=pick(source["term"], {"sku", "offerTermCode", "effectiveDate", "termAttributes"}),
                        dimension=pick(source["dimension"], {"rateCode", "description", "beginRange", "endRange", "unit", "pricePerUnit", "appliesTo"}))
    elif kind == "aws_unpriced_product":
        evidence = pick(source, {"sku", "productFamily", "attributes"})
    elif kind in ("deepinfra_model", "historical_native_model"):
        evidence = pick(source, MODEL_FIELDS)
        if row["provider"] == "ovhcloud":
            usage = source.get("metadata", {}).get("usage_information")
            if isinstance(usage, dict):
                evidence["metadata"] = dict(usage_information=pick(usage, {"pricing", "rate_limit", "status", "statuses"}))
    elif kind == "historical_oracle_sku":
        evidence = pick(source, {'partNumber', 'metricName', 'displayName', 'serviceCategory', 'currencyCodeLocalizations'})
    elif kind == "historical_nebius_flavor":
        evidence = dict(model=pick(source['model'], MODEL_FIELDS | {'vendor'}), flavor=pick(source['flavor'], {
            'model_id', 'model_type', 'model_name', 'model_description', 'label', 'regions', 'external_provider',
            'context_window_k', 'max_model_len', 'input_price_per_million_tokens', 'output_price_per_million_tokens', 'quantization'}))
    elif kind == "historical_provider_route":
        evidence = dict(model=pick(source["model"], MODEL_FIELDS), route=pick(source["route"], {"provider", "pricing", "status", "context_length", "task", "supports_tools", "supports_structured_output"}))
    elif kind in ("deepinfra_table_row", "historical_document_row"):
        evidence = dict(headers=cells(source["headers"]), cells=cells(source["cells"]), alignment_verified=source["alignment_verified"])
        if "unit_context" in source:
            evidence["unit_context"] = source["unit_context"]
    elif kind in ("historical_pdf_page", "historical_document_text"):
        evidence = pick(source, {"text", "headings", "block_start", "block_end", "fenced_code", "alignment_verified", "extraction"})
    else:
        raise ValueError("Historical assertion needs explicit publication review")
    label = next((source[k] for k in ("model_name", "name", "display_name", "displayName", "title") if isinstance(source.get(k), str)), None)
    if not label and source.get("cells"):
        label = source["cells"][0].get("text")
    if not label and kind == "aws_sku_dimension":
        label = source["dimension"].get("description")
    if not label and source.get("text"):
        label = source["text"][:160]
    return dict(id=row["id"], provider=row["provider"], native_id=row["native_id"], label=(label or row["native_id"])[:240],
                capture_id=row["capture_id"], assertion_type=kind, identity_scope=pick(row["identity_scope"], SCOPE_FIELDS),
                source_pointer=row["source_pointer"], source_reported_effective_at=row["source_reported_effective_at"],
                extractor=row["extractor"], review_status="unreviewed_historical", comparison_eligible=False, evidence=evidence)


def project(root):
    manifest, rows, snapshot_sha256 = read_snapshot(root)  # Complete hashes, witnesses and re-extraction, fail closed.
    captures, assertions, checks, corrections = [], [], [], []
    coverage = {r["capture_id"]: r for r in rows if r["kind"] == "coverage" and r.get("capture_id")}
    for row in rows:
        kind = row["kind"]
        if kind == "capture":
            cov = coverage[row["id"]]
            captures.append(dict(id=row["id"], provider=row["provider"], source_kind=row["source_kind"],
                source_url=public_url(row["source_url"]), replay_url=public_url(row["replay_url"]) if row["replay_url"] else None,
                retrieved_at=row["retrieved_at"], archive_capture_at=row["archive_capture_at"], source_published_at=row["source_published_at"],
                source_sha256=row["raw"]["content_sha256"], scope=pick(row["request_scope"], REQUEST_FIELDS),
                state=cov["state"], assertion_count=cov["assertion_count"], returned_entries=cov.get("returned_entries"),
                cap_reached=cov.get("cap_reached", False)))
        elif kind == "assertion":
            assertions.append(project_assertion(row))
        elif kind == "coverage" and row.get("capture_id") is None:
            checks.append(dict(id=row["id"], provider=row["provider"], state=row["state"],
                checked_at=row.get("checked_at"), checked_date=row.get("checked_date"), recorded_at=row.get("recorded_at"),
                source_url=public_url(row["source_url"]), target_url=public_url(row["target_url"]) if row.get("target_url") else None,
                archive_capture_at=row.get("archive_capture_at"), http_status=row["http_status"],
                transport_exit_code=row.get("transport_exit_code"), comparison_eligible=False))
        elif kind == "correction":
            corrections.append({k: row[k] for k in ("id", "assertion_id", "supersedes", "reason", "recorded_at")})
    return dict(schema_version=1, snapshot_sha256=snapshot_sha256,
                captures=captures, assertions=assertions, checks=checks, corrections=corrections)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Write the verified projection as bounded-record JSONL instead of one stdout JSON value")
    args = parser.parse_args()
    payload = project(args.ledger_dir)
    if args.output:
        write_projection(args.output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def write_projection(path, payload):
    """Internal build bridge only; never copies warehouse JSONL into the app."""
    kinds = {"capture": "captures", "assertion": "assertions", "check": "checks", "correction": "corrections"}
    meta = dict(schema_version=1, snapshot_sha256=payload["snapshot_sha256"],
                counts={key: len(payload[key]) for key in kinds.values()})
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(kind="metadata", value=meta), ensure_ascii=False, separators=(",", ":")) + "\n")
        for kind, key in kinds.items():
            for value in payload[key]:
                line = json.dumps(dict(kind=kind, value=value), ensure_ascii=False, separators=(",", ":"))
                if len(line.encode("utf-8")) > 1024 * 1024:
                    raise ValueError("Historical projection bridge record exceeds cap")
                handle.write(line + "\n")


if __name__ == "__main__":
    main()
