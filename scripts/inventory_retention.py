"""Source-specific semantic state versus compact observation provenance.

Only Google's *latest*, unbounded Cloud Billing SKU requests have rolling
pricingInfo.effectiveTime values. Historical ranges and every other effective
date remain semantic. Original source records and hashes are never modified.
"""
from collections import Counter
from datetime import datetime, timedelta
import re
from urllib.parse import parse_qs, urlparse


CATALOG_FIELDS = ("schema_version", "parser_version", "provider", "source_kind", "records", "billing_notes")


def latest_google_request(provider, source_kind, urls):
    if provider != "vertex" or source_kind not in ("api", "api+documentation"):
        return False
    sku_urls = []
    for value in urls or []:
        url = urlparse(value)
        if url.hostname != "cloudbilling.googleapis.com":
            continue
        if url.scheme != "https" or url.username or url.password or url.port not in (None, 443):
            return False
        if re.fullmatch(r"/v1/services/[A-Za-z0-9_-]+/skus", url.path):
            sku_urls.append(url)
        elif url.path != "/v1/services":
            return False  # An unfamiliar billing endpoint cannot prove latest scope.
    # A new/unknown query parameter must be reviewed, not silently treated as
    # latest pricing. This also excludes explicit startTime/endTime requests.
    allowed = {"currencyCode", "pageSize", "pageToken"}
    return bool(sku_urls) and all(set(parse_qs(url.query, keep_blank_values=True)) <= allowed for url in sku_urls)


def google_latest_time(record, observed_at=None):
    """Recognize a single latest SKU observation, not a schedule or document."""
    if not record or record.get("provider") != "vertex" or record.get("kind") != "sku":
        return None
    service = record.get("scope", {}).get("service", "")
    if not isinstance(service, str) or not re.fullmatch(r"services/[A-Za-z0-9_-]+", service) or not isinstance(record.get("native_id"), str) or not record["native_id"].startswith(service + "/skus/"):
        return None
    infos = record.get("billing", {}).get("pricing_info")
    if not isinstance(infos, list) or len(infos) != 1 or not isinstance(infos[0], dict):
        return None
    value = infos[0].get("effectiveTime")
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?Z", value):
        return None
    try:
        effective = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if observed_at is not None:
            observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            age = observed - effective
            # Past timestamps remain exact as-of provenance under the verified
            # unbounded request contract, even when the API exceeds its advertised
            # 12-hour age. Preserve that discrepancy as a warning, not a tariff.
            # The run precedes fetching; do not suppress genuine future dates.
            if age < -timedelta(minutes=20):
                return None
    except (AttributeError, TypeError, ValueError):
        return None
    if any(rate.get("conditions", {}).get("effective_time") != value for rate in record.get("rates", [])):
        return None
    return value


def semantic_record(record, latest_google=False, observed_at=None):
    if not latest_google or observed_at is None or google_latest_time(record, observed_at) is None:
        return record
    # Copy only the two known observation paths. Unknown fields, formulas,
    # currency/FX, regions, tiers and genuine effective dates are still compared.
    info = {k: v for k, v in record["billing"]["pricing_info"][0].items() if k != "effectiveTime"}
    billing = dict(record["billing"], pricing_info=[info])
    rates = [dict(rate, conditions={k: v for k, v in rate["conditions"].items() if k != "effective_time"})
             for rate in record.get("rates", [])]
    return dict(record, billing=billing, rates=rates)


def catalog_metadata(catalog):
    result = {key: catalog[key] for key in CATALOG_FIELDS if key != "records"}
    if "google_pricing_time_mode" in catalog:
        result["google_pricing_time_mode"] = catalog["google_pricing_time_mode"]
    return result


def catalog_semantics(catalog):
    result = catalog_metadata(catalog)
    latest = catalog.get("google_pricing_time_mode") == "latest"
    result["records"] = [semantic_record(record, latest, catalog.get("google_pricing_observed_at")) for record in catalog["records"]]
    return result


def previous_catalog_semantics(catalog):
    # Schema-1 catalogs predate the explicit mode. Their recorded request URLs
    # establish the same unbounded API contract; never infer it from dates alone.
    if "google_pricing_time_mode" not in catalog and latest_google_request(catalog.get("provider"), catalog.get("source_kind"), catalog.get("source_urls")):
        catalog = dict(catalog, google_pricing_time_mode="latest", google_pricing_observed_at=catalog["changed_at"])
    return catalog_semantics(catalog)


def google_pricing_observation(catalog):
    if catalog.get("google_pricing_time_mode") != "latest" or not isinstance(catalog.get("google_pricing_observed_at"), str):
        return None
    times = {record["id"]: google_latest_time(record, catalog.get("google_pricing_observed_at")) for record in catalog["records"]}
    times = {key: value for key, value in times.items() if value is not None}
    if not times:
        return None
    # One timestamp covers almost all SKUs. Preserve every differing value
    # exactly; no assumption of uniform timestamps is used for reconstruction.
    counts = Counter(times.values())
    default = min(counts, key=lambda value: (-counts[value], value))
    observed = datetime.fromisoformat(catalog["google_pricing_observed_at"].replace("Z", "+00:00"))
    older = sum(observed - datetime.fromisoformat(value.replace("Z", "+00:00")) > timedelta(hours=12) for value in times.values())
    return dict(default_effective_time=default, record_count=len(times), older_than_documented_window_count=older,
                exceptions={key: value for key, value in sorted(times.items()) if value != default})
