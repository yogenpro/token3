"""Public USD consumption meters, East US billing location; no credentials."""
import json
import re
from urllib.parse import quote, urlparse
from .common import fetch_text, number, observation, parse_or_archive, snapshot
from .public_pricing import metadata, require_models, today

# Capture every public OpenAI service meter in East US for the full inventory.
# The dashboard parser below still selects only reviewed canonical offerings.
FILTER = "contains(productName, 'OpenAI') and armRegionName eq 'eastus'"
SOURCE = "https://prices.azure.com/api/retail/prices?$filter=" + quote(FILTER, safe="")
API_IDS = {"5.4": "gpt-5.4-2026-03-05", "5.4 mini": "gpt-5.4-mini-2026-03-17"}
SKU = re.compile(r"(5\.4(?: mini)?) (longco )?(pp )?(cd )?(inp|opt) (gl|dz)")


def parse(body, aliases, as_of=None):
    as_of = as_of or today()
    document = json.loads(body)
    if document.get("NextPageLink"):
        raise ValueError("Azure pagination is incomplete")
    groups = {}
    for row in document["Items"]:
        match = SKU.fullmatch(row["skuName"].lower())
        if match is None or row.get("type") != "Consumption" or row.get("isPrimaryMeterRegion") is not True:
            continue
        model, long, priority, cached, direction, geo = match.groups()
        if API_IDS[model] not in aliases:
            continue
        if row["currencyCode"] != "USD" or row["unitOfMeasure"] != "1M" or row["tierMinimumUnits"] != 0 or row["armRegionName"] != "eastus":
            raise ValueError("Azure meter currency, units, tier or location changed")
        effective = row["effectiveStartDate"]
        if effective[:10] > as_of.isoformat():
            continue
        if cached and direction != "inp":
            raise ValueError("Unexpected Azure cached-output meter")
        key = (model, bool(long), "priority" if priority else "standard", geo)
        field = "cache" if cached else "input" if direction == "inp" else "output"
        rates = groups.setdefault(key, {})
        rate = number(row["retailPrice"])
        previous = rates.get(field)
        if previous is None or effective > previous[0]:
            rates[field] = (effective, rate)
        elif effective == previous[0] and rate != previous[1]:
            raise ValueError("Conflicting Azure meters")
    records = []
    for (model, long, tier, geo), values in groups.items():
        if not {"input", "output", "cache"}.issubset(values):
            raise ValueError("Incomplete Azure input/output/cache meter group")
        if long and model == "5.4 mini":
            raise ValueError("Unreviewed Azure mini long-context pricing")
        minimum = 272001 if long else 0
        maximum = 272000 if model == "5.4" and not long else None
        region = "global (eastus billing)" if geo == "gl" else "US data zone (eastus billing)"
        records.append(observation("azure", API_IDS[model], values["input"][1], values["output"][1], SOURCE,
            cache_read_per_million=values["cache"][1], service_tier=tier, region=region,
            min_input_tokens=minimum, max_input_tokens=maximum,
            variant="long prompt" if long else "short prompt" if maximum else "standard",
            pricing_notes="Azure OpenAI consumption list prices, billed in East US. Global and US Data Zone deployments are separate. Cached-input meters are separate from regular input. Batch, provisioned capacity, reservations and negotiated rates are excluded. Verify endpoint context/output limits with Azure.",
            **metadata("gpt-" + model.replace(" ", "-"), cloud=True)))
    require_models(records, API_IDS.values(), aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    items, page_count, page_urls = [], 0, []
    url = SOURCE
    for _ in range(20):
        page_urls.append(url)
        body = fetch_text(url)
        page = json.loads(body)
        page_count += 1
        items.extend(page["Items"])
        url = page.get("NextPageLink")
        if not url:
            break
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "prices.azure.com" or not parsed.path.startswith("/api/retail/prices"):
            raise ValueError("Untrusted Azure pagination link")
    else:
        raise ValueError("Azure pagination exceeded 20 pages")
    # Hash and archive the complete assembled response, not just the first page.
    body = json.dumps(dict(Items=items, page_count=page_count))
    result = parse_or_archive(body, SOURCE, parse, aliases)
    result.source_urls = page_urls
    return result
