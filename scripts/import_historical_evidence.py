"""Offline historical import. Preview by default; --apply commits a validated ledger."""
import argparse
import json
from pathlib import Path
import tempfile

from .historical_ledger import DEFAULT_ROOT, ingest, sha
from .historical_sources import MAX_BYTES, archive_time, json_source


def _body(path, expected_hash, expected_bytes=None):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("Unsafe or oversized staged historical body")
    raw = path.read_bytes()
    if sha(raw) != expected_hash or (expected_bytes is not None and len(raw) != expected_bytes):
        raise ValueError("Staged historical source hash/bytes differ")
    return raw


def from_input(path):
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Historical import manifest exceeds cap")
    data = json_source(path.read_bytes())
    if set(data) != {"schema_version", "sources"} or data["schema_version"] != 1 or not isinstance(data["sources"], list):
        raise ValueError("Unsupported historical import manifest")
    descriptors = []
    for source in data["sources"]:
        if set(source) != {"label", "body_path", "body_sha256", "metadata"}:
            raise ValueError("Invalid staged source fields")
        relative = Path(source["body_path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe staged body path")
        body_path = path.parent / relative
        if not body_path.resolve().is_relative_to(path.parent.resolve()) or any(p.is_symlink() for p in [body_path] + list(body_path.parents) if p != path.parent):
            raise ValueError("Staged source escapes input directory")
        descriptors.append(dict(label=source["label"], body=_body(body_path, source["body_sha256"]), metadata=source["metadata"]))
    return descriptors


def from_research_probe(path):
    """Translate the dated local research receipts; never invent missing timestamps."""
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Research probe exceeds cap")
    probe = json_source(path.read_bytes())
    if probe.get("schema") != 1 or probe.get("research_only") is not True or probe.get("production_imported") is not False:
        raise ValueError("Unsupported research staging manifest")
    descriptors = []

    def add(label, provider, kind, receipt, scope, source_url=None, archive=None, digest=None):
        source_path = Path(receipt["local_body_path"])
        if source_path.resolve().parent != (path.parent / "bodies").resolve() or source_path.parent.is_symlink():
            raise ValueError("Research body must be in its staging bodies directory")
        raw = _body(source_path, receipt["body_sha256"], receipt["body_bytes"])
        if receipt.get("status") != "retrieved":
            raise ValueError("Unsuccessful source cannot become a capture")
        url = source_url or receipt["url"]
        data = json_source(raw) if kind.startswith("aws_") else None
        meta = dict(provider=provider, source_kind=kind, source_url=url,
                    retrieved_at=receipt["retrieved_at"], request_scope=scope,
                    source_published_at=data.get("publicationDate") if data is not None else None,
                    archive_capture_at=archive_time(archive) if archive else None, archive_digest=digest,
                    replay_url="https://web.archive.org/web/{}id_/{}".format(archive, url) if archive else None)
        descriptors.append(dict(label=label, metadata=meta, body=raw))

    for service, index in probe["aws_indexes"].items():
        add("aws-index-" + service, "bedrock", "aws_version_index", index["receipt"], dict(service=service))
    for i, query in enumerate(probe["archive_queries"]):
        add("archive-index-" + str(i), "deepinfra", "archive_index", query["receipt"], dict(target_url=query["seed"]))
    index_labels = {q["seed"]: "archive-index-" + str(i) for i, q in enumerate(probe["archive_queries"])}
    aws = sorted([r for r in probe["results"] if r["provider"] == "bedrock"],
                 key=lambda r: (r["service"], r["version_scope"]["versionEffectiveBeginDate"], r["version"]))
    archived = sorted([r for r in probe["results"] if r["provider"] == "deepinfra"], key=lambda r: (r["capture_at"], r["label"]))
    for row in aws:
        if row["status"] != "valid_json":
            raise ValueError("Research batch contains an unsuccessful AWS file")
        scope = dict(service=row["service"], region="us-east-1", version=row["version"], version_scope=row["version_scope"],
                     index_label="aws-index-" + row["service"])
        add(row["label"], "bedrock", "aws_price_list", row["receipt"], scope)
    for row in archived:
        if row["status"] not in ("valid_json", "replayed_unparsed_document"):
            raise ValueError("Research batch contains an unsuccessful archive replay")
        kind = "deepinfra_api" if row["kind"] == "deepinfra-api" else "deepinfra_html"
        add(row["label"], "deepinfra", kind, row["receipt"], dict(index_label=index_labels[row["original_url"]]),
            source_url=row["original_url"], archive=row["capture_at"], digest=row["digest"])
    return descriptors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input", type=Path, action="append", help="Portable schema-1 source-descriptor manifest; repeat for one atomic batch")
    inputs.add_argument("--research-probe", type=Path, help="Import the dated AWS/DeepInfra research staging receipts")
    parser.add_argument("--ledger-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--checks", type=Path, help="Bounded explicit discovery-check rows, committed atomically with the batch")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--dry-run", action="store_true", help="Default: validate in an isolated temporary ledger")
    args = parser.parse_args()
    if args.input and len(args.input) > 16:
        parser.error("At most 16 bounded source manifests may form one batch")
    descriptors = [source for path in args.input for source in from_input(path)] if args.input else from_research_probe(args.research_probe)
    checks = None
    if args.checks:
        if args.checks.stat().st_size > 4 * 1024 * 1024:
            parser.error("Discovery checks exceed cap")
        checks = json_source(args.checks.read_bytes())
        if not isinstance(checks, list):
            parser.error("Discovery checks must be an array")
    if args.apply:
        result = ingest(args.ledger_dir, descriptors, checks=checks)
    else:
        with tempfile.TemporaryDirectory(prefix="token3-historical-preview-") as directory:
            result = ingest(Path(directory), descriptors, checks=checks)
    print(json.dumps(dict(applied=args.apply, counts=result["counts"], segments=len(result["segments"]))))


if __name__ == "__main__":
    main()
