"""Explicit, reversible native-history migration; default is a read-only report.

python -m scripts.compact_inventory_history --apply
python -m scripts.compact_inventory_history --verify
python -m scripts.compact_inventory_history --restore-archive /path/original.jsonl
"""
import argparse
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .inventory_retention import latest_google_request
from .native_history import compact_history, iter_archive_lines, load_manifest, verify_archive, verify_reconstruction
from .normalize import ROOT


def git_catalog_proofs(repo):
    path = "data/provider_catalogs/vertex.json"
    commits = subprocess.check_output(["git", "log", "--all", "--format=%H", "--", path], cwd=repo, text=True).splitlines()
    proofs = {}
    for commit in reversed(commits):
        result = subprocess.run(["git", "show", commit + ":" + path], cwd=repo, text=True, capture_output=True)
        if result.returncode:
            continue
        catalog = json.loads(result.stdout)
        urls = catalog.get("source_urls", [])
        if not latest_google_request("vertex", catalog.get("source_kind"), urls):
            continue
        # Do not persist credential-bearing witness URLs, including document URLs.
        for value in urls:
            url = urlparse(value)
            if url.scheme != "https" or url.username or url.password or any(
                key != "pageToken" and any(word in key.lower() for word in ("key", "token", "secret", "signature", "credential", "authorization"))
                for key in parse_qs(url.query, keep_blank_values=True)
            ):
                raise ValueError("Unsafe historical witness URL")
        key = catalog["catalog_sha256"]
        proofs.setdefault(key, dict(catalog_sha256=key, source_sha256=catalog["source_sha256"], source_kind=catalog["source_kind"],
                                    source_urls=urls, revision=catalog["revision"], observed_at=catalog.get("google_pricing_observed_at", catalog["changed_at"]),
                                    witness_commit=commit, witness_path=path,
                                    witness_git_blob=subprocess.check_output(["git", "rev-parse", commit + ":" + path], cwd=repo, text=True).strip()))
    return proofs


@contextmanager
def collection_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".collect.lock").open("a") as handle:
        try:
            import fcntl
        except ImportError:
            raise RuntimeError("Migration requires an exclusive collection lock; use a Unix environment")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--apply", action="store_true")
    actions.add_argument("--verify", action="store_true")
    actions.add_argument("--restore-archive", type=Path)
    args = parser.parse_args()
    with collection_lock(args.data_dir):
        if args.restore_archive:
            manifest = load_manifest(args.data_dir)
            verify_archive(args.data_dir, manifest)
            # Never overwrite a current data file, archived file, or existing audit output.
            with args.restore_archive.open("xb") as output:
                for line in iter_archive_lines(args.data_dir, manifest):
                    output.write(line)
            report = dict(restored_original_bytes=manifest["archive"]["bytes"], sha256=manifest["archive"]["sha256"])
        elif args.verify:
            report = verify_reconstruction(args.data_dir)["migration"]
        else:
            proofs = {} if (args.data_dir / "inventory_history/manifest.json").exists() else git_catalog_proofs(ROOT)
            report = compact_history(args.data_dir, proofs, apply=args.apply)
        print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
