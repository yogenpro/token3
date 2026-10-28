"""Reproducible best-effort price-coverage audit; never promotes native evidence.

Counts are assertion/capture counts, not unique models or price changes. Document
candidates require an aligned price column; PDF/narrative amounts are leads only.
"""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

from .historical_ledger import DEFAULT_ROOT, canonical, read_asset, read_snapshot, sha
from .historical_reports import DEFAULT, load
from .historical_recovery_audit import archive_namespace

ROOT = Path(__file__).resolve().parents[1]
NUMBER = re.compile(r"(?:^|[\s$€£¥(])([0-9]+(?:\.[0-9]+)?)(?=$|[\s/)%*†‡,])")
PRICE_HEADER = re.compile(r"price|pricing|cost|\$|usd|eur|credits?|dbu|neurons?", re.I)
UNIT_HEADER = re.compile(r"tokens?|million|\b1m\b|\b1k\b|/\s*[hm]|per\b", re.I)


def numeric(value):
    if isinstance(value, bool) or value is None:
        return False
    try:
        number = Decimal(str(value))
        return number.is_finite() and number >= 0
    except InvalidOperation:
        return False


def price_values(value):
    if isinstance(value, dict):
        return any(price_values(v) for k, v in value.items() if not re.search(r"context|limit|max_tokens|timestamp|created|updated|private|discount|multiplier|rate_per_|retention|duration|valid_until", k, re.I))
    if isinstance(value, list):
        return any(price_values(v) for v in value)
    return numeric(value)


def price_evidence(row):
    """Return a diagnostic grade; source expressions remain unnormalized."""
    kind, source = row["assertion_type"], row["source_record"]
    if kind == 'historical_oracle_sku':
        return 'structured_native' if any(numeric(p.get('value')) for c in source.get('currencyCodeLocalizations', [])
            if isinstance(c, dict) for p in c.get('prices', []) if isinstance(p, dict)) else None
    if kind == 'historical_nebius_flavor':
        return 'structured_native' if any(numeric(source['flavor'].get(k)) for k in ('input_price_per_million_tokens', 'output_price_per_million_tokens')) else None
    if kind == "aws_sku_dimension":
        return "structured_native" if price_values(source["dimension"].get("pricePerUnit")) else None
    if kind in {"deepinfra_model", "historical_native_model", "historical_provider_route"}:
        if row.get("provider") == "ovhcloud":
            usage = source.get("metadata", {}).get("usage_information", {})
            if isinstance(usage, dict) and price_values(usage.get("pricing")):
                return "structured_native"
        source = source.get("route", source)
        prices = source.get("pricing")
        if prices is not None and price_values(prices):
            return "structured_native"
        if any(price_values(source.get(k)) for k in ("input_token_price_per_m", "output_token_price_per_m")):
            return "structured_native"
        return None
    if kind in {"deepinfra_table_row", "historical_document_row"}:
        if source.get("alignment_verified") is not True or len(source["headers"]) != len(source["cells"]):
            return None
        headings = " ".join(row["identity_scope"].get("headings", []))
        table = " ".join(c.get("text", "") for c in source["headers"]) + " " + source.get("unit_context", "")
        for header, cell in zip(source["headers"], source["cells"]):
            h, text = header.get("text", ""), cell.get("text", "").strip()
            # Numeric context lengths, shutdown dates, percentages and model-ID
            # digits are not prices. Require an explicit price/amount column.
            price_column = bool(PRICE_HEADER.search(h)) or bool(re.search(r"input|output|cached?", h, re.I) and PRICE_HEADER.search(headings + " " + table) and UNIT_HEADER.search(headings + " " + table))
            if price_column and NUMBER.search(text) and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?%", text):
                return "document_price_candidate"
        return None
    return None


def build(root=DEFAULT_ROOT, reports=DEFAULT, pdf_research=None, embedded_research=None, *, snapshot=None):
    manifest, rows, snapshot_sha256 = read_snapshot(root) if snapshot is None else snapshot
    sources = {r["id"]: r for r in rows if r["kind"] == "capture"}
    providers = json.loads((ROOT / "data/provider_inventory.json").read_bytes())["providers"]
    stats = {p["id"]: dict(name=p["name"], captures=0, archived_bodies=0, assertions=0,
        structured_native_price_assertions=0, document_price_candidates=0, price_capture_count=0, pdf_layout_candidates=0, pdf_layout_capture_count=0,
        embedded_price_candidates=0, embedded_price_capture_count=0,
        decoded_document_price_candidates=0,
        earliest_price_source_date=None, latest_price_source_date=None, report_claims=0, conflicting_report_claims=0,
        capture_states={}, retained_lookup_checks={}, outstanding_replay_targets=0, unsupported_or_ambiguous_captures=0,
        price_evidence_examples=[]) for p in providers}
    states, checks = defaultdict(Counter), defaultdict(Counter)
    price_captures = defaultdict(set)
    retained = set()
    unresolved = defaultdict(set)
    for source in sources.values():
        p = source["provider"]; stats[p]["captures"] += 1
        if source["archive_capture_at"]:
            stats[p]["archived_bodies"] += 1
            retained.add((archive_namespace(source), p, source["archive_capture_at"], source["source_url"], source["archive_digest"]))
    for row in rows:
        p = row.get("provider")
        if p not in stats:
            continue
        entry = stats[p]
        if row["kind"] == "coverage":
            if row["capture_id"] is None:
                checks[p][row["state"]] += 1
                if row.get("archive_capture_at"):
                    unresolved[p].add((archive_namespace(row), p, row["archive_capture_at"], row["target_url"], row["archive_digest"]))
            else:
                states[p][row["state"]] += 1
                if row["state"] in {"document_text_only_ambiguous_tables", "pdf_text_only", "unparsed_text_encoding", "unparsed_or_incomplete_catalog", "unsupported_pdf_body", "unparsed_pdf_limit", "no_structured_tables", "truncated_archived_response"}:
                    entry["unsupported_or_ambiguous_captures"] += 1
        elif row["kind"] == "assertion":
            entry["assertions"] += 1
            grade = price_evidence(row)
            if not grade:
                continue
            field = "structured_native_price_assertions" if grade == "structured_native" else "document_price_candidates"
            entry[field] += 1
            price_captures[p].add(row["capture_id"])
            source = sources[row["capture_id"]]
            # Do not use recent retrieval to manufacture older price evidence.
            # Report exact source timestamps and their basis; no effective date.
            value = source["archive_capture_at"] or source["source_published_at"]
            if value:
                if not entry["earliest_price_source_date"] or value < entry["earliest_price_source_date"]:
                    entry["earliest_price_source_date"] = value
                if not entry["latest_price_source_date"] or value > entry["latest_price_source_date"]:
                    entry["latest_price_source_date"] = value
            if len(entry["price_evidence_examples"]) < 3:
                entry["price_evidence_examples"].append(dict(assertion_id=row["id"], capture_id=row["capture_id"], native_id=row["native_id"], grade=grade,
                    source_url=source["source_url"], replay_url=source["replay_url"], archive_capture_at=source["archive_capture_at"],
                    source_published_at=source["source_published_at"], reported_effective_at=row["source_reported_effective_at"]))
    if pdf_research:
        document = json.loads(Path(pdf_research).read_bytes())
        if (document.get("policy") != "historical-pdf-layout-research-v1" or
                document.get("ledger_manifest_sha256") != snapshot_sha256):
            raise ValueError("PDF research does not match this ledger snapshot")
        pdf_captures = defaultdict(set)
        expected_pdf = {}
        seen_pdf = set()
        for candidate in document["candidates"]:
            source = sources.get(candidate["capture_id"])
            if source and source["id"] not in expected_pdf:
                from .historical_pdf_research import capture_candidates
                expected_pdf[source["id"]] = {row["id"]: row for row in capture_candidates(source, read_asset(Path(root), source["raw"], "sources"))}
            if (candidate["id"] in seen_pdf or not source or candidate["provider"] != "snowflake" or source["provider"] != "snowflake" or
                    expected_pdf.get(source["id"], {}).get(candidate["id"]) != candidate or
                    candidate["id"] != sha(canonical({k: v for k, v in candidate.items() if k != "id"})) or
                    candidate["source_sha256"] != source["raw"]["content_sha256"] or
                    candidate["archive_capture_at"] != source["archive_capture_at"] or
                    candidate["source_url"] != source["source_url"] or
                    candidate["review_status"] != "unreviewed_layout_candidate" or candidate["comparison_eligible"] is not False):
                raise ValueError("PDF research candidate provenance differs")
            seen_pdf.add(candidate["id"])
            stats["snowflake"]["pdf_layout_candidates"] += 1
            pdf_captures["snowflake"].add(source["id"])
        for p, captures in pdf_captures.items():
            stats[p]["pdf_layout_capture_count"] = len(captures)
    if embedded_research:
        from .historical_embedded_research import capture_candidates
        from .historical_research_files import read_report
        document = read_report(embedded_research)
        if (document.get("policy") != "historical-embedded-price-research-v1" or document.get("ledger_manifest_sha256") != snapshot_sha256):
            raise ValueError("Embedded price research does not match this ledger snapshot")
        expected, seen, priced = {}, set(), defaultdict(set)
        for candidate in document['candidates']:
            source = sources.get(candidate['capture_id'])
            if not source or source['source_kind'] not in {'archived_native_v2', 'deepinfra_html', 'arquivo_native_v3', 'commoncrawl_native_v4'}:
                raise ValueError('Embedded price candidate lacks a supported archive capture')
            if source['id'] not in expected:
                expected[source['id']] = {c['id']: c for c in capture_candidates(source, read_asset(Path(root), source['raw'], 'sources'))}
            if candidate['id'] in seen or expected[source['id']].get(candidate['id']) != candidate:
                raise ValueError('Embedded price research differs from retained source')
            seen.add(candidate['id'])
            if candidate.get('evidence_type') == 'decoded_document_row' and candidate['numeric_price_candidate']:
                stats[source['provider']]['decoded_document_price_candidates'] += 1
                priced[source['provider']].add(source['id'])
            elif price_values(candidate['amount_expression']):
                stats[source['provider']]['embedded_price_candidates'] += 1
                priced[source['provider']].add(source['id'])
        for provider, captures in priced.items():
            stats[provider]['embedded_price_capture_count'] = len(captures)
    corroboration = load(reports)
    for claim in corroboration["claims"]:
        stats[claim["provider"]]["report_claims"] += 1
        if claim["confidence"] == "conflicting_reports":
            stats[claim["provider"]]["conflicting_report_claims"] += 1
    for p, entry in stats.items():
        entry["capture_states"] = dict(states[p])
        entry["retained_lookup_checks"] = dict(checks[p])
        entry["outstanding_replay_targets"] = len(unresolved[p] - retained)
        entry["price_capture_count"] = len(price_captures[p])
        entry["status"] = "structured_native_prices" if entry["structured_native_price_assertions"] else "document_price_candidates" if entry["document_price_candidates"] or entry["decoded_document_price_candidates"] else "embedded_price_candidates" if entry["embedded_price_candidates"] else "pdf_layout_price_candidates" if entry["pdf_layout_candidates"] else "reported_prices_only" if entry["report_claims"] else "no_numeric_price_history_identified"
    return dict(schema_version=1, policy="best-effort-price-coverage-v1", ledger_manifest_sha256=snapshot_sha256,
                counts=manifest["counts"], providers=stats, report_claim_count=len(corroboration["claims"]),
                notes=["Counts are repeated source assertions, not distinct models or price changes.",
                       "Document candidates are heuristic leads, not reviewed amounts or verified model-to-rate mappings.",
                       "No numeric evidence identified is not proof that historical pricing did not exist.",
                       "Outstanding targets subtract later successful captures; original failed/deferred checks remain retained.",
                       "Dates are archive/publication witnesses, not inferred tariff-effective intervals."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--reports", type=Path, default=DEFAULT)
    parser.add_argument("--pdf-research", type=Path, help="Optional layout research bound to this exact ledger snapshot")
    parser.add_argument("--embedded-research", type=Path, help="Optional embedded price research bound to this exact ledger snapshot")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.ledger_dir, args.reports, args.pdf_research, args.embedded_research)
    args.output.write_bytes(canonical(result) + b"\n")
    print(json.dumps(dict(providers=len(result["providers"]), statuses=dict(Counter(p["status"] for p in result["providers"].values())))))


if __name__ == "__main__":
    main()
