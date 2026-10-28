"""Validate attributed best-effort historical reports, separate from native captures.

Curated sources retain short exact excerpts, not redistributed articles or an
invented full-response hash. Reports never authorize current comparison quotes.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

from .historical_projection import public_url

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "catalog/historical_reports.json"
CLASSES = {"provider_announcement", "provider_document", "provider_social", "news_report", "community_social"}
CONFIDENCE = {"provider_reported", "provider_reported_with_secondary_coverage", "single_report", "conflicting_reports"}


def day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("Historical report needs an exact day or null, not an inferred timestamp")


def validate(document, providers):
    if set(document) != {"schema_version", "policy", "sources", "claims", "leads"} or document["schema_version"] != 1 or document["policy"] != "best-effort-historical-reports-v1":
        raise ValueError("Unsupported best-effort historical report schema")
    sources = {}
    urls = set()
    for source in document["sources"]:
        if set(source) != {"id", "url", "publisher", "source_class", "published_date", "retrieved_on", "retrieval_date_zone", "excerpt", "excerpt_sha256", "evidence_extent", "independence_group"}:
            raise ValueError("Unexpected historical source fields")
        public_url(source["url"])
        if source["source_class"] not in CLASSES or source["evidence_extent"] != "short_excerpt":
            raise ValueError("Invalid report source class or evidence extent")
        if source["published_date"] is not None:
            day(source["published_date"])
        day(source["retrieved_on"])
        if source["retrieval_date_zone"] != "America/Los_Angeles":
            raise ValueError("Retain this research batch's explicit retrieval-day timezone")
        if source["published_date"] and source["published_date"] > source["retrieved_on"]:
            raise ValueError("Source publication follows retrieval")
        excerpt = source["excerpt"]
        if not isinstance(excerpt, str) or not 1 <= len(excerpt.split()) <= 25 or hashlib.sha256(excerpt.encode()).hexdigest() != source["excerpt_sha256"]:
            raise ValueError("Report excerpt is oversized or its exact-byte hash differs")
        if source["id"] in sources or source["url"] in urls or not source["independence_group"]:
            raise ValueError("Duplicate report source or missing provenance group")
        sources[source["id"]] = source
        urls.add(source["url"])
    seen = set()
    for claim in document["claims"]:
        if set(claim) != {"id", "provider", "model_label", "native_id", "reported_date", "reported_effective_date", "effective_date_source_id", "confidence", "source_ids", "currency", "currency_symbol", "rates", "conditions", "notes", "conflicts_with", "comparison_eligible", "review_status"}:
            raise ValueError("Unexpected historical claim fields")
        if claim["id"] in seen or claim["provider"] not in providers or claim["confidence"] not in CONFIDENCE:
            raise ValueError("Invalid historical claim identity/confidence")
        seen.add(claim["id"])
        if claim["comparison_eligible"] is not False or claim["review_status"] != "best_effort_historical":
            raise ValueError("Best-effort reports cannot authorize reviewed comparison prices")
        if not claim["source_ids"] or len(set(claim["source_ids"])) != len(claim["source_ids"]) or any(s not in sources for s in claim["source_ids"]):
            raise ValueError("Historical claim lacks retained source excerpts")
        selected = [sources[s] for s in claim["source_ids"]]
        classes = {s["source_class"] for s in selected}
        if claim["confidence"].startswith("provider_reported") and not classes & {"provider_announcement", "provider_document", "provider_social"}:
            raise ValueError("Provider-reported claim lacks a provider source")
        if claim["confidence"] == "provider_reported_with_secondary_coverage" and "news_report" not in classes:
            raise ValueError("Secondary coverage label lacks a news report")
        day(claim["reported_date"])
        if claim["reported_date"] not in {s["published_date"] for s in selected}:
            raise ValueError("Reported date needs an explicit source publication witness")
        if claim["reported_effective_date"] is not None:
            day(claim["reported_effective_date"])
            witness = claim["effective_date_source_id"]
            if witness not in claim["source_ids"]:
                raise ValueError("Effective day needs its explicit source excerpt witness")
            value = date.fromisoformat(claim["reported_effective_date"])
            written = f"{value.strftime('%B')} {value.day}, {value.year}"
            excerpt = sources[witness]["excerpt"]
            if written not in excerpt or not any(word in excerpt.lower() for word in ("billing", "effective", "begins", "starts")):
                raise ValueError("Effective day is not explicit in retained source excerpt")
        elif claim["effective_date_source_id"] is not None:
            raise ValueError("Null effective date cannot assert a date witness")
        if claim["currency"] is not None:
            raise ValueError("This initial report batch preserves dollar symbols without inferring ISO currency")
        if not claim["rates"] or not claim["notes"] or not isinstance(claim["conditions"], dict):
            raise ValueError("Historical report needs rates, scope and uncertainty notes")
        dimensions = set()
        for rate in claim["rates"]:
            if set(rate) != {"dimension", "amount", "unit"} or rate["dimension"] not in {"input", "output", "cache_read", "cache_write"} or rate["dimension"] in dimensions:
                raise ValueError("Ambiguous historical report rate dimensions")
            dimensions.add(rate["dimension"])
            try:
                amount = Decimal(rate["amount"])
            except (InvalidOperation, TypeError):
                raise ValueError("Historical report amount must be an exact decimal string") from None
            if not isinstance(rate["amount"], str) or not amount.is_finite() or amount < 0 or (rate["unit"] is not None and not isinstance(rate["unit"], str)):
                raise ValueError("Invalid historical report amount/unit")
    by_id = {c["id"]: c for c in document["claims"]}
    for claim in document["claims"]:
        for other in claim["conflicts_with"]:
            if other == claim["id"] or other not in by_id or by_id[other]["provider"] != claim["provider"] or claim["id"] not in by_id[other]["conflicts_with"]:
                raise ValueError("Conflicts need two retained, reciprocal claim references")
        if bool(claim["conflicts_with"]) != (claim["confidence"] == "conflicting_reports"):
            raise ValueError("Conflicting evidence cannot silently receive an unqualified confidence label")
    for lead in document["leads"]:
        if set(lead) != {"url", "source_class", "status", "supports_pricing", "notes"}:
            raise ValueError("Invalid historical source lead")
        public_url(lead["url"])
        if lead["source_class"] not in CLASSES or lead["status"] != "not_retrieved" or lead["supports_pricing"] is not False:
            raise ValueError("Unretrieved social links cannot corroborate prices")
    return document


def load(path=DEFAULT):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Curated historical reports exceed bounded file size")
    providers = {p["id"] for p in json.loads((ROOT / "data/provider_inventory.json").read_bytes())["providers"]}
    return validate(json.loads(path.read_bytes()), providers)


if __name__ == "__main__":
    data = load()
    print(json.dumps(dict(sources=len(data["sources"]), claims=len(data["claims"]), leads=len(data["leads"]), comparison_eligible=False)))
