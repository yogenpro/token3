import re
from .common import fetch_text, markdown_tables, number, observation, parse_or_archive, provider_aliases, snapshot
from .public_pricing import GEMINI_NAMES, dated_rate, require_models, section
from .markdoc import table_markdown

SOURCE = "https://ai.google.dev/gemini-api/docs/pricing"
FETCH_URL = SOURCE + ".md.txt"
TIERS = {"Standard": "standard", "Priority": "priority", "Flex": "flex"}
ADDITIONAL_MODELS = {
    "Gemini 4 Argon": "gemini-4-argon",
    "Gemini 3.6 Flash": "gemini-3.6-flash",
    "Gemini 3.1 Flash-Lite": "gemini-3.1-flash-lite",
    "Gemini 2.5 Pro": "gemini-2.5-pro",
    "Gemini 2.5 Flash": "gemini-2.5-flash",
    "Gemini 2.5 Flash-Lite": "gemini-2.5-flash-lite",
}


def text_rate(cell, as_of=None, storage=False):
    cell = cell.replace("\\", "")
    if cell.endswith(" Implicit caching only (explicit caching is not supported)."):
        cell = cell.removesuffix(" Implicit caching only (explicit caching is not supported).")
    if storage:
        cell = re.split(r"\$[0-9.]+\s*/\s*1,000,000 tokens per hour", cell)[0].strip()
    modalities = re.fullmatch(r"\$([0-9.]+) \(text / image / video\) \$[0-9.]+ \(audio\)", cell)
    return number(modalities[1]) if modalities else dated_rate(cell, as_of)


def pro_prompt_rates(cell, storage=False):
    """Review the explicit 200K schedule without consuming token-hour storage."""
    cell = cell.replace("\\", "")
    if storage:
        cell = re.split(r"\$[0-9.]+\s*/\s*1,000,000 tokens per hour", cell)[0].strip()
    match = re.fullmatch(r"\$([0-9.]+), prompts <= 200k tokens\s+\$([0-9.]+), prompts > 200k(?: tokens)?", cell)
    if match is None:
        raise ValueError("Gemini Pro Preview prompt-band pricing changed")
    return [number(value) for value in match.groups()]


def parse(body, aliases, as_of=None):
    aliases = provider_aliases(aliases, "gemini")
    original_body = body
    body = table_markdown(body)
    records = []
    for title, model in {**GEMINI_NAMES, **ADDITIONAL_MODELS}.items():
        if model not in aliases:
            continue
        model_section = section(body, title)
        pro = model in ("gemini-3.1-pro-preview", "gemini-2.5-pro")
        # Preview only publishes Standard/Batch here; Batch is not invented Flex.
        for heading, tier in ({"Standard": "standard"} if pro or title in ADDITIONAL_MODELS else TIERS).items():
            rates = {}
            for header, cells in markdown_tables(section(model_section, heading, 3)):
                if len(header) != 3 or "per 1M tokens in USD" not in header[2]:
                    raise ValueError("Gemini paid token pricing columns changed")
                label, _, paid = cells
                if label.startswith("Input price"):
                    rates["input"] = pro_prompt_rates(paid) if pro else [text_rate(paid, as_of)]
                elif label.startswith("Output price"):
                    rates["output"] = pro_prompt_rates(paid) if pro else [dated_rate(paid, as_of)]
                elif label == "Context caching price":
                    rates["cache"] = pro_prompt_rates(paid, storage=True) if pro else [None if paid == "Not available" else text_rate(paid, as_of, storage=True)]
            if "input" not in rates or "output" not in rates or "cache" not in rates:
                raise ValueError("Missing Gemini paid token rates")
            for index in range(2 if pro else 1):
                records.append(observation("gemini", model, rates["input"][index], rates["output"][index], SOURCE,
                    cache_read_per_million=rates["cache"][index], service_tier=tier, region="global",
                    min_input_tokens=200001 if pro and index else 0,
                    max_input_tokens=200000 if pro and not index else None if pro or title in ADDITIONAL_MODELS else 1048576,
                    max_output_tokens=None if pro or title in ADDITIONAL_MODELS else 65536,
                    pricing_notes="Paid text-token pricing, not the free tier. Output includes thinking. Input/output limits are separate, not a combined context window. Cache storage per token-hour, grounding/tool charges, and other modalities are excluded. Introductory rates are selected by the UTC collection date." +
                        (" Pro 3.1 is Preview; explicit <=200K/>200K prompt bands are kept separate. Endpoint capacity/output limits are unverified; customtools and Batch are not this quote." if model == "gemini-3.1-pro-preview" else "") +
                        (" Standard text scope only; audio input and token-hour storage are excluded. Endpoint capacities remain unverified." if title in ADDITIONAL_MODELS else "") +
                        (" Argon supports implicit caching only." if model == "gemini-4-argon" else "")))
    require_models(records, [*GEMINI_NAMES.values(), *ADDITIONAL_MODELS.values()], aliases)
    return snapshot(records, original_body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    return result
