"""Official AWS price-list feeds, not copied first-party model prices."""
import json
import re
from .common import fetch_text, number, observation, parse_or_archive, snapshot
from .public_pricing import require_models

SOURCE = "https://aws.amazon.com/bedrock/pricing/"
FEEDS = {name: "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{}/current/us-east-1/index.json".format(name)
         for name in ("AmazonBedrock", "AmazonBedrockFoundationModels")}
CLAUDE = {
    "Claude Sonnet 4.6 (Amazon Bedrock Edition)": "anthropic.claude-sonnet-4-6",
    "Claude Opus 4.6 (Amazon Bedrock Edition)": "anthropic.claude-opus-4-6",
    "Claude Haiku 4.5 (Amazon Bedrock Edition)": "anthropic.claude-haiku-4-5",
}
FIELDS = {"InputTokenCount": "input", "OutputTokenCount": "output", "CacheReadInputTokenCount": "cache", "CacheWriteInputTokenCount": "write"}
TOKEN_METER = re.compile(r"USE1-MP:USE1_(InputTokenCount|OutputTokenCount|CacheReadInputTokenCount|CacheWriteInputTokenCount)(_Global)?-Units")
OSS_METER = re.compile(r"USE1-gpt-oss-(120b|20b)-(input|output)-tokens")


def sku_rate(document, sku):
    terms = document["terms"]["OnDemand"][sku]
    dimensions = [dimension for term in terms.values() for dimension in term["priceDimensions"].values()]
    if len(dimensions) != 1:
        raise ValueError("AWS token SKU has ambiguous/tiered rates")
    price = dimensions[0]
    factors = {"1K tokens": 1000, "1M tokens": 1}
    if price["unit"] not in factors or price.get("beginRange") != "0" or price.get("endRange") != "Inf":
        raise ValueError("Unsupported AWS token units/ranges")
    return number(price["pricePerUnit"]["USD"]) * factors[price["unit"]]


def parse(body, aliases):
    feeds = json.loads(body)
    groups = {}
    for feed, document in feeds.items():
        if feed not in FEEDS:
            raise ValueError("Unexpected AWS pricing service")
        for sku, product in document["products"].items():
            attrs = product["attributes"]
            usage = attrs.get("usagetype", "")
            if feed == "AmazonBedrockFoundationModels":
                model = CLAUDE.get(attrs.get("servicename"))
                match = TOKEN_METER.fullmatch(usage)
                if model is None or match is None:
                    continue
                meter, global_endpoint = match.groups()
                region = "global (us-east-1 origin)" if global_endpoint else "us-east-1 (regional)"
                field = FIELDS[meter]
            else:
                match = OSS_METER.fullmatch(usage)
                if match is None or attrs.get("feature") != "On-demand Inference":
                    continue
                size, field = match.groups()
                model = "openai.gpt-oss-{}-1:0".format(size)
                region = "us-east-1"
            if model not in aliases:
                continue
            if attrs.get("regionCode") != "us-east-1":
                raise ValueError("Unexpected AWS price-list region")
            values = groups.setdefault((model, region, feed), {})
            rate = sku_rate(document, sku)
            if field in values and values[field] != rate:
                raise ValueError("Conflicting AWS token SKUs")
            values[field] = rate
    records = []
    for (model, region, feed), rates in groups.items():
        required = {"input", "output", "cache", "write"} if feed == "AmazonBedrockFoundationModels" else {"input", "output"}
        if not required.issubset(rates):
            raise ValueError("AWS token SKU group is incomplete")
        records.append(observation("bedrock", model, rates["input"], rates["output"], FEEDS[feed],
            cache_read_per_million=rates.get("cache"), cache_write_per_million=rates.get("write"), region=region,
            pricing_notes="Bedrock Runtime on-demand prices from the official USD billing catalog, originating in us-east-1. Global routing and regional endpoints are separate. Where published, cache writes use a 5-minute TTL; 1-hour writes, batch, Mantle, reservations and provisioned throughput are excluded. Endpoint context/output limits are unverified."))
    expected = list(CLAUDE.values()) + ["openai.gpt-oss-120b-1:0", "openai.gpt-oss-20b-1:0"]
    require_models(records, expected, aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    documents = {name: json.loads(fetch_text(url)) for name, url in FEEDS.items()}
    body = json.dumps(documents)
    result = parse_or_archive(body, SOURCE, parse, aliases)
    result.source_urls = list(FEEDS.values())
    return result
