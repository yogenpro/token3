from .common import fetch_text, markdown_tables, observation, parse_or_archive, snapshot
from .public_pricing import GEMINI_NAMES, dated_rate, require_models, section

SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
FETCH_URL = SOURCE + ".md.txt"
TIERS = {"Standard": "standard", "Priority": "priority", "Flex": "flex"}


def parse(body, aliases, as_of=None):
    records = []
    for title, model in GEMINI_NAMES.items():
        if model not in aliases:
            continue
        model_section = section(body, title)
        for heading, tier in TIERS.items():
            rates = {}
            for header, cells in markdown_tables(section(model_section, heading, 3)):
                if len(header) != 3 or "per 1M tokens in USD" not in header[2]:
                    raise ValueError("Gemini paid token pricing columns changed")
                label, _, paid = cells
                if label.startswith("Input price"):
                    rates["input"] = dated_rate(paid, as_of)
                elif label.startswith("Output price"):
                    rates["output"] = dated_rate(paid, as_of)
                elif label == "Context caching price":
                    rates["cache"] = None if paid == "Not available" else dated_rate(paid, as_of, storage=True)
            if "input" not in rates or "output" not in rates or "cache" not in rates:
                raise ValueError("Missing Gemini paid token rates")
            records.append(observation("gemini", model, rates["input"], rates["output"], SOURCE,
                cache_read_per_million=rates["cache"], service_tier=tier, region="global",
                max_input_tokens=1048576, max_output_tokens=65536,
                pricing_notes="Paid text-token pricing, not the free tier. Output includes thinking. Input/output limits are separate, not a combined context window. Cache storage per token-hour, grounding/tool charges, and other modalities are excluded. Introductory rates are selected by the UTC collection date."))
    require_models(records, GEMINI_NAMES.values(), aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    return result
