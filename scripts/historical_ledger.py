"""Append-only retrospective evidence warehouse, deliberately outside live history.

The ordered atomic manifest is the sole commit point. Sources retain exact bytes;
assertions and coverage are reconstructed by a versioned offline extractor.
"""
import argparse
import contextlib
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

from .historical_sources import MAX_BYTES, extract, json_source, timestamp, validate_capture, validate_discovery_failure
from .historical_profiles import profiles

POLICY = "historical-evidence-v1"
MAX_ASSET_BYTES = MAX_BYTES + 128 * 1024
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
HASH = re.compile(r"[a-f0-9]{64}\Z")
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data" / "historical_evidence"
CAPTURE_KEYS = {"kind", "id", "provider", "source_kind", "source_url", "replay_url", "retrieved_at",
                "archive_capture_at", "archive_digest", "source_published_at", "request_scope", "raw"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def record(payload):
    payload = dict(payload)
    payload.pop("id", None)
    return dict(payload, id=payload["kind"] + "-" + sha(canonical(payload)))


def asset(content, directory):
    if not content or len(content) > MAX_BYTES or directory not in ("sources", "segments"):
        raise ValueError("Historical asset is empty or exceeds cap")
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=buffer, mode="wb", mtime=0) as handle:
        handle.write(content)
    encoded = buffer.getvalue()
    suffix = "bin.gz" if directory == "sources" else "jsonl.gz"
    reference = dict(path="{}/{}.{}".format(directory, sha(encoded), suffix), sha256=sha(encoded), bytes=len(encoded),
                     content_sha256=sha(content), uncompressed_bytes=len(content))
    return reference, encoded


def _safe_path(root, relative):
    root = Path(root)
    if root.is_symlink() or root.resolve() != root.absolute():
        raise ValueError("Ledger root cannot traverse symlinks or parent segments")
    path = root / relative
    for part in [path] + list(path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError("Historical asset cannot traverse symlinks")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Unsafe historical path")
    return path


def read_asset(root, reference, directory):
    fields = {"path", "sha256", "bytes", "content_sha256", "uncompressed_bytes"}
    if directory == "segments":
        fields.add("record_count")
    if set(reference) != fields:
        raise ValueError("Invalid historical asset metadata")
    suffix = "bin.gz" if directory == "sources" else "jsonl.gz"
    digest = reference.get("sha256")
    if not isinstance(digest, str) or not HASH.fullmatch(digest) or reference["path"] != "{}/{}.{}".format(directory, digest, suffix):
        raise ValueError("Unsafe historical asset reference")
    for key, limit in (("bytes", MAX_ASSET_BYTES), ("uncompressed_bytes", MAX_BYTES)):
        if type(reference[key]) is not int or not 0 < reference[key] <= limit:
            raise ValueError("Invalid historical asset size")
    if not isinstance(reference["content_sha256"], str) or not HASH.fullmatch(reference["content_sha256"]):
        raise ValueError("Invalid historical content hash")
    path = _safe_path(root, reference["path"])
    if path.stat().st_size != reference["bytes"]:
        raise ValueError("Historical asset byte count differs")
    encoded = path.read_bytes()
    if sha(encoded) != digest:
        raise ValueError("Historical asset checksum differs")
    with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as handle:
        content = handle.read(MAX_BYTES + 1)
    if len(content) != reference["uncompressed_bytes"] or sha(content) != reference["content_sha256"]:
        raise ValueError("Historical source reconstruction differs")
    return content


def _atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".ledger-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _immutable(root, reference, encoded):
    path = _safe_path(root, reference["path"])
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("Immutable historical asset differs")
    else:
        _atomic(path, encoded)


def empty_manifest():
    return dict(schema_version=1, policy=POLICY, segments=[], counts=dict(capture=0, assertion=0, coverage=0, correction=0))


def validate_rows(rows, source_reader):
    """Fail on incomplete extraction, forged assertions, broken witnesses or references."""
    seen, context, expected = {}, {}, {}
    expected_order, actual_order = [], []
    counts = dict(capture=0, assertion=0, coverage=0, correction=0)
    for row in rows:
        kind = row.get("kind")
        if kind not in counts or record(row) != row or row["id"] in seen:
            raise ValueError("Invalid/duplicate historical record identity")
        if kind == "capture":
            if set(row) != CAPTURE_KEYS:
                raise ValueError("Unexpected historical capture fields")
            validate_capture(row)
            raw = source_reader(row["raw"])
            context[row["id"]] = (row, raw)
            assertions, coverage = extract(row, raw, context)
            derived = [record(a) for a in assertions] + [record(coverage)]
            for item in derived:
                expected[item["id"]] = item
                expected_order.append(item["id"])
        elif kind == "coverage" and row.get("capture_id") is None:
            if row.get('provenance') == 'historical_discovery_v4':
                from .historical_commoncrawl import validate_check
                validate_check(row, context)
            elif row.get('provenance') == 'historical_discovery_v3':
                from .historical_arquivo import validate_check
                validate_check(row, context)
            elif row.get("provenance") == "historical_discovery_v2":
                from .historical_expansion import validate_check
                validate_check(row, context)
            else:
                validate_discovery_failure(row)
        elif kind in ("assertion", "coverage"):
            if row != expected.pop(row["id"], None):
                raise ValueError("Historical extraction differs from exact retained source")
            actual_order.append(row["id"])
        else:
            keys = {"kind", "id", "assertion_id", "supersedes", "reason", "recorded_at"}
            if set(row) != keys or not isinstance(row["reason"], str) or not 0 < len(row["reason"].strip()) <= 2000:
                raise ValueError("Invalid historical correction")
            timestamp(row["recorded_at"])
            old, new = seen.get(row["supersedes"]), seen.get(row["assertion_id"])
            if old is None or new is None or old["kind"] != "assertion" or new["kind"] != "assertion" or old == new:
                raise ValueError("Correction needs two retained assertions")
            identity = lambda r: (r["provider"], r["native_id"], r["identity_scope"], r["assertion_type"])
            if identity(old) != identity(new):
                raise ValueError("Correction cannot alias unrelated historical identities")
            # Corrections point backwards in ledger order, precluding supersession cycles.
            if list(seen).index(old["id"]) >= list(seen).index(new["id"]):
                raise ValueError("Historical correction must point to a later assertion")
        seen[row["id"]] = row
        counts[kind] += 1
    if expected or expected_order != actual_order:
        raise ValueError("Incomplete or reordered historical extraction")
    return counts


def read_ledger(root=DEFAULT_ROOT, manifest=None):
    root = Path(root).absolute()
    if manifest is None:
        path = _safe_path(root, "manifest.json")
        if not path.exists():
            raise ValueError("Historical ledger does not exist")
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError("Historical manifest exceeds cap")
        manifest = json_source(path.read_bytes())
    if set(manifest) != {"schema_version", "policy", "segments", "counts"} or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or manifest["policy"] != POLICY:
        raise ValueError("Unsupported historical manifest")
    refs = manifest["segments"]
    if not isinstance(refs, list) or len({r["path"] for r in refs}) != len(refs):
        raise ValueError("Duplicate historical segment references")
    rows = []
    for ref in refs:
        content = read_asset(root, ref, "segments")
        if not content.endswith(b"\n") or type(ref.get("record_count")) is not int:
            raise ValueError("Incomplete historical segment")
        lines = content.splitlines()
        if len(lines) != ref["record_count"] or not lines:
            raise ValueError("Historical segment count differs")
        rows.extend(json_source(line) for line in lines)
    cache = {}

    def source(ref):
        key = canonical(ref)
        if key not in cache:
            cache[key] = read_asset(root, ref, "sources")
        return cache[key]

    counts = validate_rows(rows, source)
    if manifest["counts"] != counts or any(type(v) is not int for v in manifest["counts"].values()):
        raise ValueError("Historical manifest totals differ")
    return manifest, rows


def read_snapshot(root=DEFAULT_ROOT):
    """Bind validated rows to the exact manifest bytes read before reconstruction."""
    root = Path(root).absolute()
    path = _safe_path(root, "manifest.json")
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Historical manifest exceeds cap")
    raw = path.read_bytes()
    manifest, rows = read_ledger(root, manifest=json_source(raw))
    return manifest, rows, sha(raw)


@contextlib.contextmanager
def locked(root):
    root = Path(root).absolute()
    _safe_path(root, "manifest.json")
    root.mkdir(parents=True, exist_ok=True)
    lock_path = _safe_path(root, ".ledger.lock")
    with lock_path.open("a") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another historical ledger writer is running") from exc
        yield


def _commit(root, manifest, old_rows, new_rows, sources, segment_cap=MAX_BYTES):
    if type(segment_cap) is not int or not 0 < segment_cap <= MAX_BYTES:
        raise ValueError("Invalid historical segment cap")
    old_ids = {r["id"] for r in old_rows}
    pending = []
    for row in new_rows:
        if row["id"] not in old_ids:
            pending.append(row)
            old_ids.add(row["id"])
    if not pending:
        return manifest
    source_map = {canonical(ref): raw for ref, raw in sources}

    def source(ref):
        return source_map[canonical(ref)] if canonical(ref) in source_map else read_asset(root, ref, "sources")

    counts = validate_rows(old_rows + pending, source)
    chunks, current, count = [], bytearray(), 0
    for row in pending:
        line = canonical(row) + b"\n"
        if len(line) > segment_cap:
            raise ValueError("Single historical record exceeds segment cap")
        if current and len(current) + len(line) > segment_cap:
            chunks.append((bytes(current), count))
            current, count = bytearray(), 0
        current.extend(line)
        count += 1
    if current:
        chunks.append((bytes(current), count))
    refs = list(manifest["segments"])
    for ref, raw in sources:
        rebuilt, encoded = asset(raw, "sources")
        if rebuilt != ref:
            raise ValueError("Historical source ref differs")
        _immutable(root, ref, encoded)
    for content, count in chunks:
        ref, encoded = asset(content, "segments")
        ref["record_count"] = count
        _immutable(root, ref, encoded)
        refs.append(ref)
    candidate = dict(schema_version=1, policy=POLICY, segments=refs, counts=counts)
    encoded = canonical(candidate) + b"\n"
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise ValueError("Historical manifest exceeds cap")
    read_ledger(root, manifest=candidate)  # Verify persisted bytes before advancing the commit point.
    _atomic(_safe_path(root, "manifest.json"), encoded)
    return candidate


def ingest(root, descriptors, segment_cap=MAX_BYTES, checks=None):
    """Offline import of ordered public-source descriptors; retry-safe and all-or-nothing."""
    root = Path(root).absolute()
    with locked(root):
        if (root / "manifest.json").exists():
            manifest, old = read_ledger(root)
        else:
            manifest, old = empty_manifest(), []
        context = {r["id"]: (r, read_asset(root, r["raw"], "sources")) for r in old if r["kind"] == "capture"}
        pending, sources, labels = [], [], {}
        for descriptor in descriptors:
            meta, raw = dict(descriptor["metadata"]), descriptor["body"]
            if not isinstance(raw, bytes):
                raise ValueError("Historical import needs exact bytes")
            ref, _ = asset(raw, "sources")
            scope = dict(meta["request_scope"])
            if "index_label" in scope:
                scope["index_capture_id"] = labels[scope.pop("index_label")]
            meta.update(kind="capture", request_scope=scope, raw=ref)
            capture = record(meta)
            if set(capture) != CAPTURE_KEYS:
                raise ValueError("Unexpected import metadata")
            if descriptor["label"] in labels:
                raise ValueError("Duplicate import label")
            labels[descriptor["label"]] = capture["id"]
            context[capture["id"]] = (capture, raw)
            assertions, coverage = extract(capture, raw, context)
            pending.extend([capture] + [record(a) for a in assertions] + [record(coverage)])
            sources.append((ref, raw))
        for check in checks or []:
            check = dict(check)
            if "index_label" in check:
                check["index_capture_id"] = labels[check.pop("index_label")]
            pending.append(record(check))
        if not descriptors and not checks:
            raise ValueError("Empty historical import")
        return _commit(root, manifest, old, pending, sources, segment_cap)


def correct(root, assertion_id, supersedes, reason, recorded_at):
    root = Path(root).absolute()
    with locked(root):
        manifest, old = read_ledger(root)
        row = record(dict(kind="correction", assertion_id=assertion_id, supersedes=supersedes,
                          reason=reason, recorded_at=recorded_at))
        return _commit(root, manifest, old, [row], [])


def record_discovery_failure(root, source_url, checked_date, http_status=None, recorded_at=None):
    root = Path(root).absolute()
    with locked(root):
        manifest, old = read_ledger(root)
        # Repeating the same operator report is idempotent; retain its first recording time.
        for row in old:
            if (row["kind"] == "coverage" and row.get("provenance") == "operator_reported_discovery_check"
                    and (row["source_url"], row["checked_date"], row["http_status"]) == (source_url, checked_date, http_status)):
                return manifest
        row = record(dict(kind="coverage", capture_id=None, provider="deepinfra", source_url=source_url,
                          checked_date=checked_date, http_status=http_status, state="request_failed",
                          provenance="operator_reported_discovery_check", comparison_eligible=False,
                          recorded_at=recorded_at or datetime.now(timezone.utc).isoformat()))
        return _commit(root, manifest, old, [row], [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-dir", type=Path, default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify", help="Check every retained byte, extraction, reference and count")
    failure = sub.add_parser("record-discovery-failure", help="Retain a dated failed lookup without inventing a capture")
    failure.add_argument("--source-url", required=True)
    failure.add_argument("--checked-date", required=True)
    failure.add_argument("--http-status", type=int)
    inspect = sub.add_parser("inspect", help="Inspect one exact source-native identity")
    inspect.add_argument("--provider", choices=sorted({"bedrock", "deepinfra"} | set(profiles())), required=True)
    identity = inspect.add_mutually_exclusive_group(required=True)
    identity.add_argument("--native-id")
    identity.add_argument("--sku", help="Exact AWS SKU; includes all retained term/rate dimensions")
    restore = sub.add_parser("restore", help="Restore a capture's exact original bytes to a new file")
    restore.add_argument("--capture-id", required=True)
    restore.add_argument("--output", type=Path, required=True)
    correction = sub.add_parser("correct", help="Append an explicit supersession without erasing assertions")
    for name in ("assertion-id", "supersedes", "reason", "recorded-at"):
        correction.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.command == "record-discovery-failure":
        result = record_discovery_failure(args.ledger_dir, args.source_url, args.checked_date, args.http_status)
        print(json.dumps(result["counts"]))
        return
    if args.command == "correct":
        manifest = correct(args.ledger_dir, args.assertion_id, args.supersedes, args.reason, args.recorded_at)
        print(json.dumps(manifest["counts"]))
        return
    manifest, rows = read_ledger(args.ledger_dir)
    if args.command == "verify":
        print(json.dumps(dict(policy=POLICY, counts=manifest["counts"], segments=len(manifest["segments"]))))
    elif args.command == "inspect":
        if args.sku and args.provider != "bedrock":
            parser.error("--sku applies only to bedrock")
        captures = {r["id"]: r for r in rows if r["kind"] == "capture"}
        assertions = [r for r in rows if r["kind"] == "assertion" and r["provider"] == args.provider
                      and (r["identity_scope"].get("sku", r["native_id"] if r["assertion_type"] == "aws_unpriced_product" else None) == args.sku
                           if args.sku else r["native_id"] == args.native_id)]
        ids = {r["id"] for r in assertions}
        print(json.dumps(dict(assertions=assertions, captures=[captures[k] for k in dict.fromkeys(r["capture_id"] for r in assertions)],
                              corrections=[r for r in rows if r["kind"] == "correction" and (r["assertion_id"] in ids or r["supersedes"] in ids)]), indent=2))
    else:
        capture = next((r for r in rows if r["kind"] == "capture" and r["id"] == args.capture_id), None)
        if capture is None:
            parser.error("Capture does not exist")
        if args.output.absolute().is_relative_to(args.ledger_dir.absolute()):
            parser.error("Restore output must be outside the ledger")
        content = read_asset(args.ledger_dir, capture["raw"], "sources")
        with args.output.open("xb") as handle:
            handle.write(content)
        print(json.dumps(dict(restored_bytes=len(content), sha256=sha(content))))


if __name__ == "__main__":
    main()
