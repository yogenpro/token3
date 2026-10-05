"""Run with python3 -m scripts.collect. Optional API keys enable API-first pricing sources."""
import argparse
import csv
import gzip
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from providers import anthropic, azure, bedrock, deepinfra, fireworks, gemini, groq, novita, openai, together, vertex
from providers.common import safe_error
from .detect_changes import detect_changes, event
from .normalize import ROOT, PRICE_FIELDS, catalog, normalize, price_signature
from .provider_inventory import inventory_document as legacy_inventory_document, prepare_source
from .inventory_storage import history_content, inventory_document, prepare_catalog
from .archive_reference import lookup_reference
from .catalog_inventory import canonical

PROVIDERS = {"deepinfra": deepinfra, "novita": novita, "together": together, "fireworks": fireworks, "groq": groq,
             "openai": openai, "anthropic": anthropic, "gemini": gemini, "vertex": vertex, "bedrock": bedrock, "azure": azure}
PROVIDER_NAMES = {"deepinfra": "DeepInfra", "novita": "Novita", "together": "Together AI", "fireworks": "Fireworks", "groq": "Groq",
                  "openai": "OpenAI API", "anthropic": "Anthropic API", "gemini": "Google Gemini API", "vertex": "Google Vertex AI", "bedrock": "Amazon Bedrock", "azure": "Azure OpenAI"}
SOURCE_KINDS = {"deepinfra": "api", "novita": "api", "azure": "api", "bedrock": "price_list"}
HISTORY_FIELDS = ("offering_id", "observed_at") + PRICE_FIELDS + ("currency", "source_url", "source_sha256")


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def read_history(path):
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in PRICE_FIELDS:
            row[field] = float(row[field]) if row[field] != "" else None
    return rows


def atomic_write(path, content):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(str(temporary), str(path))


def save_json(path, value):
    atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def apply_snapshot(provider, result, aliases, observed_at, offerings, latest, history, changes):
    # Validate the ENTIRE provider result before modifying any state. A broken
    # parser must never retire offerings or replace good prices with partial data.
    normalized = [normalize(record, aliases, observed_at, result.source_sha256) for record in result.records]
    if not normalized:
        raise ValueError("Refusing an empty snapshot")
    ids = [offering["id"] for offering, _ in normalized]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate offerings in provider snapshot")
    if any(offering["provider"] != provider for offering, _ in normalized):
        raise ValueError("Provider identity does not match collector")
    previous_history = {row["offering_id"]: row for row in history}
    for offering, price in normalized:
        offering_id = offering["id"]
        old = offerings.get(offering_id)
        offering["first_observed_at"] = old["first_observed_at"] if old else observed_at
        changes.extend(detect_changes(old, offering, latest.get(offering_id), price, observed_at))
        previous = previous_history.get(offering_id)
        # Change-only history. Freshness is updated in latest/status, not by
        # duplicating an unchanged price on every day. Existing rows stay intact.
        if previous is None or price_signature(previous) != price_signature(price):
            history.append(price.copy())
        offerings[offering_id] = offering
        latest[offering_id] = price
    if result.authoritative_catalog:
        for offering in offerings.values():
            if offering["provider"] == provider and offering["active"] and offering["id"] not in ids:
                offering["active"] = False
                changes.append(event("offering_removed", offering, observed_at))
    return len(normalized)


def run(data_dir, selected=None, dry_run=False, strict=False, archive_legacy=False, response_dir=None, archive_lookups=False):
    models, aliases = catalog()
    data_dir.mkdir(parents=True, exist_ok=True)
    offerings = {row["id"]: row for row in load_json(data_dir / "offerings.json", [])}
    latest = {row["offering_id"]: row for row in load_json(data_dir / "latest_prices.json", [])}
    history = read_history(data_dir / "price_history.csv")
    changes = load_json(data_dir / "changes.json", [])
    previous_status = load_json(data_dir / "status.json", {"providers": []})
    statuses = {row["id"]: row for row in previous_status["providers"]}
    previous_inventory = load_json(data_dir / "provider_inventory.json", {"providers": []})
    source_index = {row["id"]: row for row in previous_inventory.get("providers", [])}
    source_artifacts = {}
    inventory_events = []
    response_manifest = []
    checks = []
    inventory_touched = False
    selected = selected or list(PROVIDERS)
    observed_at = utc_now()
    failures = 0
    secrets = [os.environ.get(key, "") for key in ("TOGETHER_API_KEY", "FIREWORKS_API_KEY", "GOOGLE_CLOUD_BILLING_API_KEY")]
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(PROVIDERS[name].collect, aliases): name for name in selected}
        for future in as_completed(futures):
            name = futures[future]
            previous = statuses.get(name, {})
            source_metadata = {}
            try:
                result = future.result()
                exposed = (result.source_payload or "") + canonical([result.source_url, result.source_urls])
                if any(secret and secret in exposed for secret in secrets):
                    raise ValueError("Source unexpectedly contains a configured credential; refusing to persist it")
                if result.parse_error:
                    for secret in secrets:
                        if secret:
                            result.parse_error = result.parse_error.replace(secret, "[redacted]")
                result.source_kind = result.source_kind or SOURCE_KINDS.get(name, "documentation")
                source_metadata = dict(source_kind=result.source_kind, fallback_reason=result.fallback_reason,
                                       source_urls=result.source_urls or [result.source_url], source_url=result.source_url)
                # Public-source diagnostics only. Authenticated model catalogs
                # can contain account-scoped fields; never upload those bodies
                # as publicly downloadable workflow artifacts.
                public_response = not (name in ("together", "fireworks", "vertex") and result.source_kind in ("api", "api+documentation"))
                if response_dir is not None and not dry_run and public_response:
                    response_dir.mkdir(parents=True, exist_ok=True)
                    response_path = response_dir / (name + ".source.gz")
                    response_path.write_bytes(gzip.compress(result.source_payload.encode(), mtime=0))
                    response_manifest.append(dict(provider=name, observed_at=observed_at, source_urls=source_metadata["source_urls"],
                                                  source_sha256=result.source_sha256, file=response_path.name))
                if archive_legacy:
                    source_row, artifact = prepare_source(name, PROVIDER_NAMES[name], result, observed_at, data_dir, source_index)
                else:
                    source_row, artifact, native_events = prepare_catalog(name, PROVIDER_NAMES[name], result, observed_at, data_dir, source_index)
                    inventory_events.extend(native_events)
                    if artifact and archive_lookups and not dry_run:
                        reference = lookup_reference(result, observed_at)
                        source_row["archive_reference"] = reference
                        artifact["archive_reference"] = reference
                    print("{}: {} full-inventory records; {} new inventory events".format(PROVIDER_NAMES[name], source_row["record_count"], len(native_events)))
                source_index[name] = source_row
                if artifact:
                    source_artifacts[data_dir / source_row["latest_path"]] = artifact
                inventory_touched = True
                if result.parse_error:
                    raise ValueError("Fetched source retained for debugging; curated parser failed: {}".format(result.parse_error))
                count = apply_snapshot(name, result, aliases, observed_at, offerings, latest, history, changes)
                statuses[name] = dict(id=name, name=PROVIDER_NAMES[name], state="ok", last_attempt_at=observed_at,
                                      last_success_at=observed_at, offering_count=count,
                                      source_sha256=result.source_sha256, authoritative_catalog=result.authoritative_catalog, error=None,
                                      **source_metadata)
                print("{}: {} offerings collected ({})".format(PROVIDER_NAMES[name], count, result.source_kind))
                if result.fallback_reason:
                    print("{}: SOURCE FALLBACK — {}".format(PROVIDER_NAMES[name], result.fallback_reason))
            except Exception as exc:
                failures += 1
                error_message = safe_error(exc, secrets)
                statuses[name] = dict(id=name, name=PROVIDER_NAMES[name], state="error", last_attempt_at=observed_at,
                                      last_success_at=previous.get("last_success_at"), offering_count=previous.get("offering_count", 0),
                                      source_url=source_metadata.get("source_url", previous.get("source_url", PROVIDERS[name].SOURCE)),
                                      source_urls=source_metadata.get("source_urls", previous.get("source_urls")),
                                      source_kind=source_metadata.get("source_kind", previous.get("source_kind")),
                                      fallback_reason=source_metadata.get("fallback_reason"), source_sha256=previous.get("source_sha256"),
                                      authoritative_catalog=previous.get("authoritative_catalog", False), error=error_message)
                if not archive_legacy and name in source_index:
                    source_index[name] = dict(source_index[name], last_attempt_at=observed_at, last_attempt_state="error", last_attempt_error=error_message)
                    inventory_touched = True
                print("{}: FAILED; previous data retained. {}".format(PROVIDER_NAMES[name], error_message[:300]))
            checks.append(dict(provider=name, observed_at=observed_at, state=statuses[name]["state"],
                               catalog_sha256=source_index.get(name, {}).get("catalog_sha256"),
                               source_kind=statuses[name].get("source_kind"), error=statuses[name].get("error")))
    status = dict(schema_version=1, last_run_at=observed_at,
                  first_observed_at=min((row["observed_at"] for row in history), default=None),
                  observation_count=len(history), providers=sorted(statuses.values(), key=lambda row: row["id"]))
    changes = sorted({row["id"]: row for row in changes}.values(), key=lambda row: (row["observed_at"], row["id"]), reverse=True)
    if not dry_run:
        if inventory_events:
            path = data_dir / "inventory_history.jsonl"
            atomic_write(path, history_content(path, inventory_events))
        check_path = data_dir / "collection_checks.jsonl"
        before = check_path.read_text() if check_path.exists() else ""
        atomic_write(check_path, before + "".join(canonical(row) + "\n" for row in sorted(checks, key=lambda r:r["provider"])))
        if response_dir is not None:
            response_dir.mkdir(parents=True, exist_ok=True)
            save_json(response_dir / "manifest.json", response_manifest)
        for path, artifact in source_artifacts.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            save_json(path, artifact)
        if inventory_touched:
            document = legacy_inventory_document(source_index, observed_at) if archive_legacy else inventory_document(source_index, observed_at)
            save_json(data_dir / "provider_inventory.json", document)
        save_json(data_dir / "status.json", status)
        if offerings:
            save_json(data_dir / "models.json", models)
            save_json(data_dir / "offerings.json", sorted(offerings.values(), key=lambda row: row["id"]))
            save_json(data_dir / "latest_prices.json", sorted(latest.values(), key=lambda row: row["offering_id"]))
            save_json(data_dir / "price_history.json", history)  # Derived cache; CSV is the history of record.
            save_json(data_dir / "changes.json", changes)
            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=HISTORY_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(history)
            atomic_write(data_dir / "price_history.csv", buffer.getvalue())
    print("{}{} observations; {} change events; {} failed providers".format("Dry run: " if dry_run else "Saved: ", len(history), len(changes), failures))
    return 1 if not offerings or failures == len(selected) or (strict and failures) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", action="append", choices=sorted(PROVIDERS), help="Limit to a provider; may be repeated")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--dry-run", action="store_true", help="Validate and summarize without writing observations")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero if any provider fails")
    parser.add_argument("--response-dir", type=Path, help="Transient gzipped source responses, kept outside Git")
    parser.add_argument("--archive-lookups", action="store_true", help="Best-effort verified public-document Wayback references on catalog changes")
    args = parser.parse_args()
    # Actions concurrency protects hosted runs. flock also protects local runs.
    args.data_dir.mkdir(parents=True, exist_ok=True)
    with (args.data_dir / ".collect.lock").open("a") as lock:
        try:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass  # On Windows, run only one collector process at a time.
        except BlockingIOError:
            parser.error("Another collection is already running against this data directory")
        raise SystemExit(run(args.data_dir, args.provider, args.dry_run, args.strict,
                             response_dir=args.response_dir, archive_lookups=args.archive_lookups))


if __name__ == "__main__":
    main()
