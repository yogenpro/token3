"""Explicit, resumable public archive discovery; stages evidence, never writes the ledger.

No credentials, inference calls, archive submissions or automatic scheduled runs.
Offline validation/import is a separate command.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlencode, urljoin, urlsplit

from .historical_profiles import PROFILE, archive_query, normalized, profiles, source_spec
from .historical_sources import MAX_BYTES, archive_time, json_source


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(body):
    return hashlib.sha256(body).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
        handle.write(json.dumps(value, indent=2).encode() + b"\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def metadata(provider, kind, url, retrieved_at, scope, stamp=None, archive_digest=None):
    return dict(provider=provider, source_kind=kind, source_url=url, retrieved_at=retrieved_at,
                archive_capture_at=archive_time(stamp) if stamp else None, archive_digest=archive_digest,
                source_published_at=None, request_scope=dict(profile=PROFILE, **scope),
                replay_url="https://web.archive.org/web/{}id_/{}".format(stamp, url) if stamp else None)


def adopt_results(stage, path):
    """Accept bounded external transport receipts; perform the same byte/digest checks.

    Useful when an execution environment grants network access only to individual
    attached commands. This does not fetch, trust HTTP status alone or import data.
    """
    rows = json.loads(path.read_bytes())
    if not isinstance(rows, list) or len(rows) > 5000:
        raise ValueError("Invalid external transport batch")
    jobs = json.loads((stage / "plan.json").read_bytes())["jobs"]
    discovery = Discovery(stage, MAX_BYTES, 1)
    counts = {}
    for row in rows:
        if set(row) != {"index", "http_status", "exit_code", "retrieved_at", "body_path"} or type(row["index"]) is not int or not 0 <= row["index"] < len(jobs):
            raise ValueError("Invalid external transport receipt")
        job = jobs[row["index"]]
        source_spec(job["url"], job["provider"])
        replay = "https://web.archive.org/web/{}id_/{}".format(job["stamp"], job["url"])
        receipt_path = stage / "requests" / (digest((job["provider"] + "\n" + replay).encode()) + ".json")
        old = json.loads(receipt_path.read_bytes()) if receipt_path.exists() else {}
        if old.get("state") == "retrieved":
            continue
        receipt = dict(provider=job["provider"], url=replay, label=job["label"], checked_at=row["retrieved_at"],
            attempts=old.get("attempts", 0) + 1, http_status=row["http_status"] or None, curl_exit_code=row["exit_code"],
            previous_attempts=old.get("previous_attempts", []) + ([{k:v for k,v in old.items() if k != "previous_attempts"}] if old else []))
        if row["http_status"] == 200 and row["exit_code"] == 0:
            body = stage / row["body_path"]
            if body.is_symlink() or body.resolve().parent != (stage / "direct").resolve() or not 0 < body.stat().st_size <= MAX_BYTES:
                raise ValueError("Unsafe external transport body")
            raw = body.read_bytes()
            if base64.b32encode(hashlib.sha1(raw).digest()).decode() == job["digest"]:
                body_path, sha = discovery.blob(raw)
                receipt.update(state="retrieved", body_path=body_path, body_sha256=sha, body_bytes=len(raw),
                               retrieved_at=row["retrieved_at"], final_url=replay)
            else:
                receipt["state"] = "digest_mismatch"
        else:
            receipt["state"] = "fetch_failed"
        save(receipt_path, receipt)
        counts[receipt["state"]] = counts.get(receipt["state"], 0) + 1
    return counts


class Discovery:
    def __init__(self, stage, max_bytes, max_requests):
        self.stage, self.max_bytes, self.max_requests = stage, max_bytes, max_requests
        self.used, self.requests = 0, 0
        self.guard = threading.Lock()
        for name in ("bodies", "requests"):
            (stage / name).mkdir(parents=True, exist_ok=True)

    def blob(self, raw):
        sha = digest(raw)
        path = self.stage / "bodies" / sha
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError("Staged immutable body differs")
        else:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
                handle.write(raw)
                temporary = Path(handle.name)
            temporary.replace(path)
        return "bodies/" + sha, sha

    def fetch(self, provider, url, label, expected=None, live=False):
        job = digest((provider + "\n" + url).encode())
        receipt_path = self.stage / "requests" / (job + ".json")
        if receipt_path.exists():
            old = json.loads(receipt_path.read_bytes())
            if old["state"] == "retrieved":
                path = self.stage / old["body_path"]
                if path.is_file() and digest(path.read_bytes()) == old["body_sha256"]:
                    return old
                raise ValueError("Resumed historical body is missing or corrupt")
            # Connection/DNS failures can be execution-environment failures, not vendor outages.
            # Keep every attempt and use short resumable batches rather than unbounded retries.
            limit = 4 if old.get("curl_exit_code") in (6, 7) else 2
            if old.get("attempts", 0) >= limit and old["state"] != "budget_deferred":
                return old
        else:
            old = {}
        with self.guard:
            if self.used + MAX_BYTES > self.max_bytes or self.requests >= self.max_requests:
                return dict(provider=provider, url=url, label=label, state="budget_deferred", checked_at=now(), attempts=old.get("attempts", 0))
            self.requests += 1
            self.used += MAX_BYTES  # Reserve per-worker headroom; release after each bounded request.
        previous = old.get("previous_attempts", []) + ([{k:v for k,v in old.items() if k != "previous_attempts"}] if old else [])
        row = dict(provider=provider, url=url, label=label, checked_at=now(), attempts=old.get("attempts", 0) + 1,
                   previous_attempts=previous)
        final, raw, status, exit_code = url, b"", 0, 0
        try:
            with tempfile.TemporaryDirectory(prefix="fetch-", dir=self.stage) as temp:
                for redirect in range(4):
                    p = urlsplit(final)
                    if p.scheme != "https":
                        raise ValueError("redirect_denied")
                    if live:
                        if not source_spec(final, provider).get("allow_current_document"):
                            raise ValueError("redirect_denied")
                    elif p.netloc != "web.archive.org":
                        raise ValueError("redirect_denied")
                    elif "/web/" in url and not final.startswith(url.split("id_/")[0]):
                        raise ValueError("redirect_denied")
                    body_path, headers_path = Path(temp) / "body", Path(temp) / "headers"
                    result = subprocess.run(["curl", "--disable", "--fail", "--silent", "--show-error", "--proto", "=https",
                        "--connect-timeout", "10", "--max-time", "30", "--max-filesize", str(MAX_BYTES),
                        "--user-agent", "Token3 historical evidence research (public read-only)",
                        "--dump-header", str(headers_path), "--output", str(body_path), "--write-out", "%{http_code}", final], capture_output=True)
                    exit_code = result.returncode
                    status = int(result.stdout or b"0")
                    if headers_path.exists() and headers_path.stat().st_size > 65536:
                        raise ValueError("oversized_headers")
                    if 300 <= status < 400:
                        locations = [line.split(":", 1)[1].strip() for line in headers_path.read_text(errors="replace").splitlines()
                                     if line.lower().startswith("location:")]
                        if not locations or redirect == 3:
                            raise ValueError("redirect_denied")
                        target = urljoin(final, locations[-1])
                        if target.startswith("http://web.archive.org/"):
                            target = "https://" + target[len("http://"):]
                        final = target
                        continue
                    if exit_code or status != 200:
                        row.update(state="fetch_failed", http_status=status or None, curl_exit_code=exit_code)
                        break
                    raw = body_path.read_bytes()
                    if not raw or len(raw) > MAX_BYTES:
                        raise ValueError("oversized_or_empty_body")
                    if expected and base64.b32encode(hashlib.sha1(raw).digest()).decode() != expected:
                        row.update(state="digest_mismatch", http_status=status)
                        break
                    path, sha = self.blob(raw)
                    row.update(state="retrieved", retrieved_at=now(), final_url=final, body_path=path, body_sha256=sha,
                               body_bytes=len(raw), http_status=status)
                    break
        except ValueError as exc:
            row["state"] = str(exc) if str(exc) in {"redirect_denied", "oversized_headers", "oversized_or_empty_body"} else "invalid_transport"
        finally:
            with self.guard:
                self.used -= MAX_BYTES - len(raw)
        save(receipt_path, row)
        time.sleep(0.4)
        return row

    def source(self, label, meta, receipt):
        return dict(label=label, body_path=receipt["body_path"], body_sha256=receipt["body_sha256"], metadata=meta)

    def run(self, selected, research=None, research_bodies=None):
        registry = profiles()
        old = {r["provider"]: r for r in json.loads(research.read_bytes())["providers"]} if research else {}
        sources, indexes, checks = [], [], []
        for provider in selected:
            for spec in registry[provider]["sources"]:
                url = spec["url"]
                label = provider + "-index-" + digest(url.encode())[:16]
                index_path = self.stage / (label + ".json")
                if index_path.exists():
                    value = json.loads(index_path.read_bytes())
                    raw = (self.stage / value["receipt"]["body_path"]).read_bytes()
                    if digest(raw) != value["receipt"]["body_sha256"]:
                        raise ValueError("Staged archive index differs")
                elif provider in old and normalized(old[provider]["seed_url"]) == normalized(url):
                    witness = old[provider]
                    raw = (research_bodies / (provider + "-cdx.json")).read_bytes()
                    if digest(raw) != witness["response_sha256"] or len(raw) != witness["response_bytes"]:
                        raise ValueError("Research index receipt differs")
                    path, sha = self.blob(raw)
                    receipt = dict(state="retrieved", body_path=path, body_sha256=sha, body_bytes=len(raw),
                                   retrieved_at=witness["retrieved_at"], url=witness["query_url"])
                    value = dict(provider=provider, seed=url, label=label, receipt=receipt)
                    save(index_path, value)
                else:
                    query = "https://web.archive.org/cdx/search/cdx?" + urlencode(dict(url=url, matchType="exact", output="json",
                        filter="statuscode:200", fl="timestamp,original,mimetype,statuscode,digest", limit="5001",
                        to=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")))
                    receipt = self.fetch(provider, query, label)
                    if receipt["state"] != "retrieved":
                        checks.append(receipt)
                        continue
                    raw = (self.stage / receipt["body_path"]).read_bytes()
                    value = dict(provider=provider, seed=url, label=label, receipt=receipt)
                    save(index_path, value)
                data = json_source(raw)
                if not isinstance(data, list) or (data and data[0] != ["timestamp", "original", "mimetype", "statuscode", "digest"]):
                    raise ValueError("Archive query did not return its declared index")
                archive_query(value["receipt"]["url"], provider)
                for row in data[1:]:
                    source_spec(row[1], provider)
                    archive_time(row[0])
                sources.append(self.source(label, metadata(provider, "archive_index_v2", value["receipt"]["url"],
                    value["receipt"]["retrieved_at"], dict(target_url=url)), value["receipt"]))
                indexes.append(dict(provider=provider, label=label, seed=url, rows=data[1:], cap_reached=len(data) - 1 >= 5001))
        # Interleave providers so a slow source cannot exclude all subsequent providers.
        by_provider = {p: [] for p in selected}
        seen = set()
        for index in indexes:
            for stamp, original, mime, status, cdx_digest in index["rows"]:
                key = (index["provider"], stamp, original, cdx_digest)
                if key in seen:
                    continue
                seen.add(key)
                label = index["provider"] + "-capture-" + digest((stamp + original + cdx_digest).encode())[:20]
                by_provider[index["provider"]].append(dict(provider=index["provider"], stamp=stamp, url=original,
                    mime=mime, digest=cdx_digest, index_label=index["label"], label=label))
        queues = []
        for provider in selected:
            queue = sorted(by_provider[provider], key=lambda j: (j["stamp"], j["url"]))
            queues.append(([queue[0], queue[-1]] + queue[1:-1]) if len(queue) > 1 else queue)
        jobs = [q[i] for i in range(max(map(len, queues), default=0)) for q in queues if i < len(q)]
        save(self.stage / "plan.json", dict(profile=PROFILE, providers=selected, indexes=indexes, failed_indexes=checks, jobs=jobs))

        def replay(job):
            replay_url = "https://web.archive.org/web/{}id_/{}".format(job["stamp"], job["url"])
            receipt = self.fetch(job["provider"], replay_url, job["label"], expected=job["digest"])
            return job, receipt

        results = []
        with ThreadPoolExecutor(max_workers=2) as pool:
            for n, result in enumerate(pool.map(replay, jobs), 1):
                results.append(result)
                if n % 25 == 0:
                    print(json.dumps(dict(completed=n, total=len(jobs), retrieved=sum(r[1]["state"] == "retrieved" for r in results))), flush=True)
        for job, receipt in sorted(results, key=lambda r: (r[0]["provider"], r[0]["stamp"], r[0]["url"])):
            if receipt["state"] != "retrieved":
                checks.append(dict(receipt, original_url=job["url"], index_label=job["index_label"], archive_stamp=job["stamp"], archive_digest=job["digest"]))
                continue
            meta = metadata(job["provider"], "archived_native_v2", job["url"], receipt["retrieved_at"],
                            dict(index_label=job["index_label"]), job["stamp"], job["digest"])
            sources.append(self.source(job["label"], meta, receipt))
        for provider in selected:
            for spec in registry[provider]["sources"]:
                if not spec.get("allow_current_document"):
                    continue
                label = provider + "-retrospective-" + digest(spec["url"].encode())[:16]
                receipt = self.fetch(provider, spec["url"], label, live=True)
                if receipt["state"] == "retrieved":
                    sources.append(self.source(label, metadata(provider, "public_document_v2", spec["url"], receipt["retrieved_at"],
                        dict(final_url=receipt["final_url"])), receipt))
                else:
                    checks.append(receipt)
        save(self.stage / "sources.json", dict(schema_version=1, sources=sources))
        save(self.stage / "checks.json", checks)
        summary = dict(profile=PROFILE, completed_at=now(), providers=selected, indexes=len(indexes),
                       planned_replays=len(jobs), staged_sources=len(sources), check_states={}, bytes_this_run=self.used)
        for check in checks:
            summary["check_states"][check["state"]] = summary["check_states"].get(check["state"], 0) + 1
        save(self.stage / "summary.json", summary)
        print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-dir", type=Path, required=True)
    parser.add_argument("--provider", action="append", choices=sorted(profiles()))
    parser.add_argument("--max-bytes", type=int, default=1024 * 1024 * 1024)
    parser.add_argument("--max-requests", type=int, default=5000)
    parser.add_argument("--seed-research", type=Path)
    parser.add_argument("--seed-bodies", type=Path)
    parser.add_argument("--request-index", type=int, help="Fetch one checkpointed replay in an attached execution (for constrained transports)")
    parser.add_argument("--request-count", type=int, default=1, help="Attached mode: at most 20 sequential replays")
    parser.add_argument("--adopt-results", type=Path, help="Validate per-command external transport receipts against the staged plan")
    args = parser.parse_args()
    if args.max_bytes < MAX_BYTES or not 1 <= args.max_requests <= 10000:
        parser.error("Invalid bounded discovery budget")
    args.stage_dir.mkdir(parents=True, exist_ok=True)
    if args.adopt_results:
        with (args.stage_dir / ".discovery.lock").open("a") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            print(json.dumps(adopt_results(args.stage_dir, args.adopt_results)), flush=True)
        return
    if args.request_index is not None:
        plan = json.loads((args.stage_dir / "plan.json").read_bytes())
        if not 0 <= args.request_index < len(plan["jobs"]) or not 1 <= args.request_count <= 20:
            parser.error("Request index is outside the staged plan")
        discovery = Discovery(args.stage_dir, MAX_BYTES * (args.request_count + 1), args.request_count)
        for offset, job in enumerate(plan["jobs"][args.request_index:args.request_index + args.request_count]):
            source_spec(job["url"], job["provider"])
            archive_time(job["stamp"])
            replay = "https://web.archive.org/web/{}id_/{}".format(job["stamp"], job["url"])
            result = discovery.fetch(job["provider"], replay, job["label"], expected=job["digest"])
            print(json.dumps(dict(index=args.request_index + offset, provider=job["provider"], state=result["state"], http_status=result.get("http_status"))), flush=True)
        return
    with (args.stage_dir / ".discovery.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        Discovery(args.stage_dir, args.max_bytes, args.max_requests).run(args.provider or sorted(profiles()), args.seed_research, args.seed_bodies)


if __name__ == "__main__":
    main()
