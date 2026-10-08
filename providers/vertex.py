"""Vertex AI: Cloud Billing SKU inventory plus reviewed document-based quotes."""
import hashlib
import os
import re

from .common import Collection, fetch_text, money, observation, parse_or_archive, safe_error, snapshot
from .google_billing import vertex_catalog
from .pricing_api import encode_payload
from .public_pricing import CLAUDE_NAMES, GEMINI_NAMES, PricingHTML, gemini_vertex_label, require_models, unique_records

SOURCE = "https://cloud.google.com/vertex-ai/generative-ai/pricing"
REGIONS = {"Global": "global", "us-east 5": "us-east5", "us-east5": "us-east5", "europe-west 1": "europe-west1", "europe-west1": "europe-west1", "asia-southeast1": "asia-southeast1", "asia-east1": "asia-east1"}
CLAUDE_IDS = {"claude-sonnet-4-6": "claude-sonnet-4-6", "claude-opus-4-6": "claude-opus-4-6", "claude-haiku-4-5-20251001": "claude-haiku-4-5@20251001"}


def bands(rates):
    # Each field has two prompt-length columns. Equal rates aren't distinct
    # offerings; absent long-context prices must not be extrapolated.
    if not {"input", "output", "cache"}.issubset(rates):
        raise ValueError("Incomplete Vertex token price group")
    short = {key: values[0] for key, values in rates.items()}
    long = {key: values[1] for key, values in rates.items()}
    if short["input"] is None or short["output"] is None:
        raise ValueError("Missing Vertex base rates")
    if long["input"] is None and long["output"] is None:
        return [(short, 0, 200000)]
    if long["input"] is None or long["output"] is None:
        raise ValueError("Missing Vertex long-prompt rate")
    if short == long:
        return [(short, 0, None)]
    return [(short, 0, 200000), (long, 200001, None)]


def claude_token_table(header):
    """Recognize only the reviewed 1M-token, 200K prompt-band columns.

    Global Claude tables may append a separate 100K pair for newer models.
    Column counts alone cannot establish either the unit or band boundaries.
    """
    if len(header) not in (4, 6) or header[:2] != ["Model", "Type"]:
        return False
    columns = [re.fullmatch(r"(?:Model)?Price \(/1M tokens\) (<=|=<|>) (200|100)K input tokens(?: \*+)?", label)
               for label in header[2:]]
    if any(column is None for column in columns):
        return False
    boundaries = [("short" if column[1] in ("<=", "=<") else "long", column[2]) for column in columns]
    reviewed = [("short", "200"), ("long", "200")]
    return boundaries in (reviewed, reviewed + [("short", "100"), ("long", "100")])


def parse(body, aliases, as_of=None):
    parser = PricingHTML()
    parser.feed(body)
    groups = {}
    for table in parser.tables:
        if not table["rows"]:
            continue
        header = table["rows"][0]
        gemini = len(header) == 7 and header[:3] == ["Model", "Type", "Region"] and "1M tokens" in header[3]
        claude = claude_token_table(header)
        if not gemini and not claude:
            continue
        # Ignore structurally similar tables for untracked models/products.
        relevant = any((gemini_vertex_label(row[0], as_of) if gemini else CLAUDE_IDS.get(CLAUDE_NAMES.get(row[0]))) in aliases
                       for row in table["rows"][1:] if row)
        if not relevant:
            continue
        if gemini:
            priority = "Priority" in header[3]
            flex = "Flex/Batch" in header[3]
            tier = "priority" if priority else "flex" if flex else "standard"
        else:
            tier = "standard"
            regions = [REGIONS[label] for label in table["labels"] if label in REGIONS]
            if len(regions) != 1:
                raise ValueError("Vertex Claude pricing region cannot be identified from its tab")
            # Regional Claude tables currently contain conflicting, unlabeled
            # input/output rows. Do not guess which rate applies: bootstrap
            # Claude only from the unambiguous Global tab. Gemini endpoint
            # geographies are explicit in their own table columns.
            if regions[0] != "global":
                continue
        current_model, current_type = None, None
        for cells in table["rows"][1:]:
            if len(cells) != len(header):
                raise ValueError("Vertex pricing table cell count changed")
            if cells[0]:
                current_model = gemini_vertex_label(cells[0], as_of) if gemini else CLAUDE_IDS.get(CLAUDE_NAMES.get(cells[0]))
                current_type = None
            if cells[1]:
                current_type = cells[1]
            if current_model is None or current_model not in aliases:
                continue
            # A tracked model moving to (or acquiring) a 100K schedule needs
            # explicit review, not a fallback to different/cheaper columns.
            if claude and any(money(cell, optional=True) is not None for cell in cells[4:]):
                raise ValueError("Tracked Vertex Claude model has unsupported 100K prompt-band rates: " + current_model)
            if gemini:
                region = "global" if cells[2] == "Global" else "non-global" if cells[2] in ("Non-global *", "Non-global*", "Non-global") else None
                if region is None:
                    raise ValueError("Unknown Vertex Gemini endpoint region")
                kind = "input" if current_type.startswith("Input (") else "output" if current_type.startswith("Text output") else None
                if kind is None:
                    continue
                rates = [money(c, optional=True) for c in cells[3:5]]
                cache = [money(c, optional=True) for c in cells[5:7]]
            else:
                region = regions[0]
                kind = {"Input": "input", "Output": "output", "Cache Hit": "cache", "5m Cache Write": "write"}.get(current_type)
                if kind is None:  # batch, 1h writes, and reserved capacity are not standard requests
                    continue
                rates = [money(c, optional=True) for c in cells[2:4]]
            values = groups.setdefault((current_model, tier, region), {})
            if kind in values and values[kind] != rates:
                raise ValueError("Conflicting Vertex price cells for {} / {} / {} / {}: {} vs {}".format(current_model, tier, region, kind, values[kind], rates))
            values[kind] = rates
            if gemini and kind == "input":
                values["cache"] = cache
    records = []
    for (model, tier, region), rates in groups.items():
        for values, minimum, maximum in bands(rates):
            google = model.startswith("gemini-")
            if google:
                maximum = min(maximum, 1048576) if maximum is not None else 1048576
            records.append(observation("vertex", model, values["input"], values["output"], SOURCE,
                cache_read_per_million=values.get("cache"), cache_write_per_million=values.get("write"),
                region=region, service_tier=tier, min_input_tokens=minimum, max_input_tokens=maximum,
                max_output_tokens=65536 if google else None,
                pricing_notes=("Vertex AI text-token list prices. Gemini global/non-global endpoints remain separate; Claude is scoped to the Global endpoint only. "
                    "Gemini input/output limits are separate (publisher model reference); combined context is unverified. "
                    "Claude cache-write quote uses a 5-minute TTL. Cache storage, cache-write and tool fees are excluded. "
                    "Flex uses the explicitly published shared Flex/Batch rate, not an inferred batch discount. "
                    "Dated introductory rows are selected by UTC collection date.")))
    expected = list(GEMINI_NAMES.values()) + list(CLAUDE_IDS.values())
    require_models(records, expected, aliases)
    return snapshot(unique_records(records), body, SOURCE)


def collect(aliases):
    key = os.environ.get("GOOGLE_CLOUD_BILLING_API_KEY", "").strip()
    reason = "GOOGLE_CLOUD_BILLING_API_KEY not configured"
    if key:
        try:
            catalog_payload, urls, sku_url = vertex_catalog(key)
        except Exception as exc:
            reason = "Cloud Billing catalog API unavailable: " + safe_error(exc, [key])
        else:
            # SKU names do not by themselves establish model/context/tier
            # equivalence. Keep existing reviewed quotes until that mapping is
            # curated; never silently relabel Gemini Developer API prices.
            document = None
            try:
                document = fetch_text(SOURCE)
            except Exception as exc:
                result = Collection([], sku_url, "", parse_error="Curated pricing document unavailable: " + safe_error(exc, [key]))
            else:
                result = parse_or_archive(document, SOURCE, parse, aliases)
            body = encode_payload({"cloud_billing_catalog": catalog_payload,
                                   "curated_pricing_document": {"url": SOURCE, "body": document}})
            result.source_payload = body
            result.source_sha256 = hashlib.sha256(body.encode("utf-8")).hexdigest()
            result.source_url = sku_url
            result.source_urls = urls + ([SOURCE] if document is not None else [])
            result.source_kind = "api+documentation"
            return result
    result = parse_or_archive(fetch_text(SOURCE), SOURCE, parse, aliases)
    result.source_kind = "documentation"
    result.fallback_reason = reason
    return result
