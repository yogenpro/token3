"""Bounded native-history storage and reversible, explicitly verified compaction.

The manifest is the commit point. Segments/proofs are immutable and addressed by
compressed/file SHA-256. Original migration input is retained byte-for-byte in
bounded gzip archive segments, not reclassified or discarded.
"""
import copy
import gzip
import hashlib
import io
import json
import os
import re
from pathlib import Path

from .catalog_inventory import canonical
from .inventory_retention import google_latest_time, latest_google_request, semantic_record

MAX_SEGMENT_BYTES = 16 * 1024 * 1024
MAX_COMPRESSED_BYTES = MAX_SEGMENT_BYTES + 128 * 1024
MANIFEST = "inventory_history/manifest.json"
LEGACY = "inventory_history.jsonl"
POLICY = "google-unbounded-latest-v1"
HASH = re.compile(r"[a-f0-9]{64}\Z")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(str(temporary), str(path))


def _immutable(path, content):
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("Immutable history asset differs")
    else:
        _atomic(path, content)


def _integer(value):
    return type(value) is int and value >= 0


def _path(root, ref, directory, suffix):
    digest = ref.get("sha256", "")
    expected = "inventory_history/{}/{}.{}".format(directory, digest, suffix)
    if not HASH.fullmatch(digest) or ref.get("path") != expected:
        raise ValueError("Unsafe history asset reference")
    path = Path(root) / expected
    if (not path.resolve().is_relative_to(Path(root).resolve())
            or path.resolve().parent != (Path(root) / "inventory_history" / directory).resolve() or path.is_symlink()):
        raise ValueError("Unsafe history asset path")
    return path


def _read_ref(root, ref, directory):
    path = _path(root, ref, directory, "jsonl.gz")
    if not _integer(ref.get("bytes")) or not 0 < ref["bytes"] <= MAX_COMPRESSED_BYTES:
        raise ValueError("Invalid compressed history size")
    if not _integer(ref.get("uncompressed_bytes")) or not 0 < ref["uncompressed_bytes"] <= MAX_SEGMENT_BYTES:
        raise ValueError("Invalid uncompressed history size")
    if not _integer(ref.get("event_count")) or not HASH.fullmatch(ref.get("content_sha256", "")):
        raise ValueError("Invalid history segment metadata")
    if path.stat().st_size != ref["bytes"]:
        raise ValueError("History segment byte count differs")
    encoded = path.read_bytes()
    if sha(encoded) != ref["sha256"]:
        raise ValueError("History segment checksum differs")
    with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as handle:
        content = handle.read(MAX_SEGMENT_BYTES + 1)
    if len(content) != ref["uncompressed_bytes"] or sha(content) != ref["content_sha256"]:
        raise ValueError("History segment content differs")
    if not content.endswith(b"\n"):
        raise ValueError("Incomplete history segment")
    lines = content.splitlines(keepends=True)
    if sum(bool(line.strip()) for line in lines) != ref["event_count"]:
        raise ValueError("History segment row count differs")
    return content


def load_manifest(root):
    path = Path(root) / MANIFEST
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Oversized history manifest")
    return validate_manifest(root, json.loads(path.read_text()))


def validate_manifest(root, manifest):
    if manifest.get("schema_version") != 1 or manifest.get("policy") != POLICY:
        raise ValueError("Unsupported history manifest")
    if not all(_integer(manifest.get(k)) for k in ("event_count", "observation_count")) or manifest["observation_count"] > manifest["event_count"]:
        raise ValueError("Invalid history totals")
    refs = manifest.get("segments")
    if not isinstance(refs, list) or len({r.get("path") for r in refs}) != len(refs):
        raise ValueError("Duplicate or invalid history segments")
    if sum(r.get("event_count", -1) for r in refs) != manifest["event_count"]:
        raise ValueError("Incomplete history manifest")
    legacy = Path(root) / LEGACY
    if legacy.exists():
        original = manifest.get("archive", {})
        if legacy.stat().st_size != original.get("bytes") or sha(legacy.read_bytes()) != original.get("sha256"):
            raise ValueError("Legacy history changed after compaction")
    return manifest


def load_proofs(root, manifest):
    ref = manifest["proofs"]
    path = _path(root, ref, "proofs", "json")
    if not _integer(ref.get("bytes")) or not 0 < ref["bytes"] <= 1024 * 1024 or path.stat().st_size != ref["bytes"]:
        raise ValueError("Invalid history proof size")
    content = path.read_bytes()
    if sha(content) != ref["sha256"]:
        raise ValueError("History proof checksum differs")
    document = json.loads(content)
    if document.get("schema_version") != 1 or document.get("policy") != POLICY or not isinstance(document.get("catalogs"), dict):
        raise ValueError("Invalid history proofs")
    for key, proof in document["catalogs"].items():
        if not HASH.fullmatch(key) or proof.get("catalog_sha256") != key or not latest_google_request("vertex", proof.get("source_kind"), proof.get("source_urls")):
            raise ValueError("Unverified retrospective request scope")
    return document["catalogs"]


def expand_row(row, previous, proofs):
    """Return the original JSON event and a separately scoped interpretation flag."""
    event = dict(row)
    observation = event.pop("_observation", None)
    if observation is None:
        return event, False
    old = previous.get(event.get("record_id"))
    if (event.get("provider") != "vertex" or event.get("kind") != "record_changed" or "after" in event or not old
            or observation.get("policy") != POLICY or observation.get("before_event_id") != old.get("id")
            or old.get("catalog_sha256") not in proofs or event.get("catalog_sha256") not in proofs
            or not HASH.fullmatch(observation.get("original_event_sha256", ""))
            or not google_latest_time(old.get("after"), old.get("observed_at"))):
        raise ValueError("Invalid retrospective observation reference")
    after = copy.deepcopy(old["after"])
    value = observation.get("effective_time")
    after["billing"]["pricing_info"][0]["effectiveTime"] = value
    for rate in after.get("rates", []):
        rate["conditions"]["effective_time"] = value
    if google_latest_time(after, event.get("observed_at")) != value or value is None:
        raise ValueError("Invalid retrospective observation timestamp")
    event["after"] = after
    return event, True


def update_previous(previous, event):
    if isinstance(event.get("after"), dict):
        previous[event.get("record_id")] = event
    elif event.get("kind") == "record_no_longer_listed":
        previous.pop(event.get("record_id"), None)


def iter_history(root, manifest=None):
    """Stream (original event, verified observation-only flag); support old fixtures."""
    root = Path(root)
    if manifest is None and not (root / MANIFEST).exists():
        if (root / LEGACY).exists():
            with (root / LEGACY).open("rb") as handle:
                for line in handle:
                    if line.strip():
                        row = json.loads(line)
                        if "_observation" in row:
                            raise ValueError("Observation requires a verified manifest")
                        yield row, False
        return
    manifest = load_manifest(root) if manifest is None else validate_manifest(root, manifest)
    proofs = load_proofs(root, manifest)
    previous, ids, count, observations = {}, set(), 0, 0
    for ref in manifest["segments"]:
        for line in _read_ref(root, ref, "segments").splitlines():
            if not line.strip():
                continue
            event, observation = expand_row(json.loads(line), previous, proofs)
            if not isinstance(event.get("id"), str) or event["id"] in ids:
                raise ValueError("Duplicate or invalid history event ID")
            ids.add(event["id"])
            count += 1
            observations += observation
            update_previous(previous, event)
            yield event, observation
    if count != manifest["event_count"] or observations != manifest["observation_count"]:
        raise ValueError("History totals differ")


def _segments(root, lines, directory, limit=MAX_SEGMENT_BYTES):
    if type(limit) is not int or not 0 < limit <= MAX_SEGMENT_BYTES:
        raise ValueError("Invalid history segment limit")
    refs, content, count = [], bytearray(), 0

    def flush():
        nonlocal content, count
        if not content:
            return
        raw = bytes(content)
        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=6) as handle:
            handle.write(raw)
        encoded = buffer.getvalue()
        if len(encoded) > MAX_COMPRESSED_BYTES:
            raise ValueError("Oversized compressed history segment")
        digest = sha(encoded)
        path = "inventory_history/{}/{}.jsonl.gz".format(directory, digest)
        _immutable(Path(root) / path, encoded)
        refs.append(dict(path=path, sha256=digest, bytes=len(encoded), uncompressed_bytes=len(raw), content_sha256=sha(raw), event_count=count))
        content, count = bytearray(), 0

    for line in lines:
        if not line.endswith(b"\n") or len(line) > limit:
            raise ValueError("Incomplete or oversized indivisible history row")
        if len(content) + len(line) > limit:
            flush()
        content.extend(line)
        count += bool(line.strip())
    flush()
    return refs


def compact_rows(lines, proofs):
    previous, ids = {}, set()
    for raw in lines:
        if not raw.strip():
            yield raw, False
            continue
        event = json.loads(raw)
        if not isinstance(event.get("id"), str) or event["id"] in ids or "_observation" in event:
            raise ValueError("Invalid original history event")
        ids.add(event["id"])
        old = previous.get(event.get("record_id"))
        before, after = old.get("after") if old else None, event.get("after")
        eligible = (event.get("provider") == "vertex" and event.get("kind") == "record_changed" and old is not None
                    and old.get("catalog_sha256") in proofs and event.get("catalog_sha256") in proofs
                    and google_latest_time(before, old.get("observed_at")) and google_latest_time(after, event.get("observed_at"))
                    and canonical(semantic_record(before, True, old["observed_at"])) == canonical(semantic_record(after, True, event["observed_at"])))
        if eligible:
            row = {k: v for k, v in event.items() if k != "after"}
            row["_observation"] = dict(policy=POLICY, before_event_id=old["id"], effective_time=google_latest_time(after, event["observed_at"]), original_event_sha256=sha(raw))
            yield (canonical(row) + "\n").encode(), True
        else:
            yield raw, False
        update_previous(previous, event)


def verify_archive(root, manifest=None):
    manifest = manifest or load_manifest(root)
    archive = manifest["archive"]
    refs = archive.get("segments", [])
    if not isinstance(refs, list) or len({r.get("path") for r in refs}) != len(refs):
        raise ValueError("Invalid archive segments")
    digest, size, count = hashlib.sha256(), 0, 0
    for ref in refs:
        content = _read_ref(root, ref, "archive")
        digest.update(content)
        size += len(content)
        count += ref["event_count"]
    if digest.hexdigest() != archive.get("sha256") or size != archive.get("bytes") or count != archive.get("event_count"):
        raise ValueError("Original archive differs")
    return archive


def iter_archive_lines(root, manifest):
    for ref in manifest["archive"]["segments"]:
        yield from _read_ref(root, ref, "archive").splitlines(keepends=True)


def verify_reconstruction(root, manifest=None):
    manifest = load_manifest(root) if manifest is None else validate_manifest(root, manifest)
    verify_archive(root, manifest)
    original = (line for line in iter_archive_lines(root, manifest) if line.strip())
    stored = (json.loads(line) for ref in manifest["segments"] for line in _read_ref(root, ref, "segments").splitlines() if line.strip())
    expanded = iter_history(root, manifest)
    for _ in range(manifest["archive"]["event_count"]):
        raw = next(original, None)
        row = next(stored, None)
        after = next(expanded, (None, False))[0]
        if raw is None or row is None or canonical(after) != canonical(json.loads(raw)):
            raise ValueError("Compaction changed an original observation")
        if "_observation" in row and row["_observation"]["original_event_sha256"] != sha(raw):
            raise ValueError("Original observation checksum differs")
    if next(original, None) is not None:
        raise ValueError("Archive count differs")
    # Validate the remaining, legitimately appended events and total counts too.
    for _ in expanded:
        pass
    return manifest


def compact_history(root, catalogs, apply=False, limit=MAX_SEGMENT_BYTES):
    root = Path(root)
    if (root / MANIFEST).exists():
        manifest = verify_reconstruction(root)
        if apply and (root / LEGACY).exists():
            (root / LEGACY).unlink()
        return manifest["migration"]
    source = root / LEGACY
    original = source.read_bytes()
    proofs = {key: value for key, value in catalogs.items() if key == value.get("catalog_sha256") and HASH.fullmatch(key)
              and latest_google_request("vertex", value.get("source_kind"), value.get("source_urls"))}
    observations, events, removed_bytes = 0, 0, 0
    for line, observation in compact_rows(original.splitlines(keepends=True), proofs):
        observations += observation
        events += bool(line.strip())
        removed_bytes += len(line)
    report = dict(policy=POLICY, input_sha256=sha(original), input_bytes=len(original), event_count=events,
                  observation_count=observations, compacted_uncompressed_bytes=removed_bytes)
    if not apply:
        return report
    if not original.endswith(b"\n"):
        raise ValueError("Incomplete original history")
    proof_bytes = (canonical(dict(schema_version=1, policy=POLICY, catalogs=proofs)) + "\n").encode()
    proof_path = "inventory_history/proofs/{}.json".format(sha(proof_bytes))
    _immutable(root / proof_path, proof_bytes)
    archive = _segments(root, original.splitlines(keepends=True), "archive", limit)
    segments = _segments(root, (line for line, _ in compact_rows(original.splitlines(keepends=True), proofs)), "segments", limit)
    manifest = dict(schema_version=1, policy=POLICY, event_count=events, observation_count=observations, segments=segments,
                    proofs=dict(path=proof_path, sha256=sha(proof_bytes), bytes=len(proof_bytes)), migration=report,
                    archive=dict(sha256=sha(original), bytes=len(original), event_count=events, segments=archive))
    # Validate immutable staged assets before publishing the atomic commit point.
    verify_reconstruction(root, manifest)
    if source.read_bytes() != original:
        raise ValueError("Original history changed during migration")
    _atomic(root / MANIFEST, (canonical(manifest) + "\n").encode())
    source.unlink()
    return report


def append_history(root, events):
    """Collector-only append. Caller holds .collect.lock; retries retain event IDs."""
    root = Path(root)
    events = list(events)
    for event in events:
        if not isinstance(event.get("id"), str) or not event["id"] or "_observation" in event:
            raise ValueError("Invalid collector history event; retrospective classification requires migration")
    if not (root / MANIFEST).exists():
        from .inventory_storage import history_content
        content = history_content(root / LEGACY, events).encode()
        if len(content) > MAX_SEGMENT_BYTES:
            raise ValueError("Legacy native history exceeds 16 MiB; run the explicit compaction migration")
        _atomic(root / LEGACY, content)
        return
    manifest = load_manifest(root)
    ids = {event["id"] for event, _ in iter_history(root)}
    fresh = []
    for event in events:
        if event["id"] not in ids:
            fresh.append((canonical(event) + "\n").encode())
            ids.add(event["id"])
    if not fresh:
        return
    manifest["segments"] += _segments(root, fresh, "segments")
    manifest["event_count"] += len(fresh)
    _atomic(root / MANIFEST, (canonical(manifest) + "\n").encode())
