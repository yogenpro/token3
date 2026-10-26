"""Offline preflight of a checkpointed discovery stage, with explicit unresolved coverage.

Writes portable import files and a coverage report. Never fetches, changes live
data, promotes quotes, or silently converts rejected sources into empty catalogs.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from .discover_historical_evidence import metadata, now, save
from .historical_ledger import asset, canonical, record
from .historical_profiles import PROFILE, archive_query, profiles
from .historical_sources import archive_time, extract
from .import_historical_evidence import _body


def prepare(stage):
    plan = json.loads((stage / "plan.json").read_bytes())
    if plan.get("profile") != PROFILE:
        raise ValueError("Unsupported discovery plan profile")
    selected = plan.get("providers", sorted({i["provider"] for i in plan["indexes"]}))
    if not selected or len(set(selected)) != len(selected) or any(p not in profiles() for p in selected):
        raise ValueError("Invalid discovery provider selection")
    sources, checks, context, labels = [], [], {}, {}
    stats = {p: dict(indexed=0, retrieved=0, accepted=0, assertions=0, kinds={}, states={}, earliest_archive=None, latest_archive=None)
             for p in selected}

    def accept(descriptor):
        raw = _body(stage / descriptor["body_path"], descriptor["body_sha256"])
        meta = dict(descriptor["metadata"])
        scope = dict(meta["request_scope"])
        if "index_label" in scope:
            scope["index_capture_id"] = labels[scope.pop("index_label")]
        meta.update(kind="capture", request_scope=scope, raw=asset(raw, "sources")[0])
        capture = record(meta)
        assertions, coverage = extract(capture, raw, context)
        context[capture["id"]] = (capture, raw)
        labels[descriptor["label"]] = capture["id"]
        sources.append(descriptor)
        provider = meta["provider"]
        stats[provider]["accepted"] += 1
        stats[provider]["assertions"] += len(assertions)
        states = stats[provider]["states"]
        states[coverage["state"]] = states.get(coverage["state"], 0) + 1
        for assertion in assertions:
            key = assertion["assertion_type"]
            stats[provider]["kinds"][key] = stats[provider]["kinds"].get(key, 0) + 1
        if meta["archive_capture_at"]:
            for field, func in (("earliest_archive", min), ("latest_archive", max)):
                current = stats[provider][field]
                stats[provider][field] = func(current, meta["archive_capture_at"]) if current else meta["archive_capture_at"]

    def descriptor(label, meta, receipt):
        return dict(label=label, metadata=meta, body_path=receipt["body_path"], body_sha256=receipt["body_sha256"])

    def failure(provider, source_url, target_url, receipt, state=None, job=None):
        status = receipt.get("http_status") or None
        code = receipt.get("curl_exit_code")
        if state is None:
            state = receipt.get("state", "budget_deferred")
            if state == "fetch_failed":
                state = "transport_failed" if status is None else "redirect_denied" if 300 <= status < 400 else "http_failed" if status >= 400 else "invalid_transport"
        check = dict(kind="coverage", capture_id=None, provider=provider, profile=PROFILE,
            provenance="historical_discovery_v2", source_url=source_url, target_url=target_url,
            checked_at=receipt.get("checked_at") or receipt.get("retrieved_at") or now(), state=state,
            http_status=status, transport_exit_code=code, comparison_eligible=False,
            archive_capture_at=archive_time(job["stamp"]) if job else None,
            archive_digest=job["digest"] if job else None, index_capture_id=None)
        if job:
            check.pop("index_capture_id")
            check["index_label"] = job["index_label"]
        checks.append(check)

    for receipt in plan.get("failed_indexes", []):
        provider, url = receipt["provider"], receipt["url"]
        failure(provider, url, archive_query(url, provider), receipt)
    for index in plan["indexes"]:
        staged = json.loads((stage / (index["label"] + ".json")).read_bytes())
        receipt = staged["receipt"]
        meta = metadata(index["provider"], "archive_index_v2", receipt["url"], receipt["retrieved_at"], dict(target_url=index["seed"]))
        accept(descriptor(index["label"], meta, receipt))
        stats[index["provider"]]["indexed"] += len(index["rows"])
    for job in plan["jobs"]:
        replay = "https://web.archive.org/web/{}id_/{}".format(job["stamp"], job["url"])
        path = stage / "requests" / (hashlib.sha256((job["provider"] + "\n" + replay).encode()).hexdigest() + ".json")
        receipt = json.loads(path.read_bytes()) if path.exists() else dict(state="budget_deferred")
        if receipt["state"] != "retrieved":
            failure(job["provider"], replay, job["url"], receipt, job=job)
            continue
        stats[job["provider"]]["retrieved"] += 1
        meta = metadata(job["provider"], "archived_native_v2", job["url"], receipt["retrieved_at"],
                        dict(index_label=job["index_label"]), job["stamp"], job["digest"])
        try:
            accept(descriptor(job["label"], meta, receipt))
        except (ValueError, UnicodeError, KeyError, TypeError, OSError):
            failure(job["provider"], replay, job["url"], receipt, "extractor_rejected", job)
    for provider in selected:
        profile = profiles()[provider]
        for spec in profile["sources"]:
            if not spec.get("allow_current_document"):
                continue
            url = spec["url"]
            path = stage / "requests" / (hashlib.sha256((provider + "\n" + url).encode()).hexdigest() + ".json")
            receipt = json.loads(path.read_bytes()) if path.exists() else dict(state="budget_deferred")
            if receipt["state"] != "retrieved":
                failure(provider, url, url, receipt)
                continue
            meta = metadata(provider, "public_document_v2", url, receipt["retrieved_at"], dict(final_url=receipt["final_url"]))
            try:
                accept(descriptor(provider + "-retrospective", meta, receipt))
            except (ValueError, UnicodeError, KeyError, TypeError, OSError):
                failure(provider, url, url, receipt, "extractor_rejected")
    for check in checks:
        field = "unresolved_" + check["state"]
        stats[check["provider"]][field] = stats[check["provider"]].get(field, 0) + 1
    report = dict(schema_version=1, profile=PROFILE, prepared_at=now(), providers=stats,
                  planned_replays=len(plan["jobs"]), accepted_captures=len(sources), unresolved_checks=len(checks),
                  states=dict(Counter(c["state"] for c in checks)),
                  coverage_note="Selected source URLs only. Indexed, retrieved, parsed, priced and reviewed are separate; gaps are not delistings.")
    (stage / "validated-sources.json").write_bytes(canonical(dict(schema_version=1, sources=sources)) + b"\n")
    (stage / "validated-checks.json").write_bytes(canonical(checks) + b"\n")
    save(stage / "coverage-report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-dir", type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.stage_dir)
    print(json.dumps({k: v for k, v in report.items() if k != "providers"}))


if __name__ == "__main__":
    main()
