from .common import fetch_text, markdown_tables, observation, parse_or_archive, provider_aliases, snapshot
from .public_pricing import CLAUDE_NAMES, metadata, mtok, require_models

SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
FETCH_URL = SOURCE + ".md"
HEADER = ["model", "base input tokens", "5m cache writes", "1h cache writes", "cache hits and refreshes", "output tokens"]


def parse(body, aliases):
    aliases = provider_aliases(aliases, "anthropic")
    records = []
    for header, cells in markdown_tables(body):
        if [c.lower() for c in header] != HEADER:
            continue
        label = cells[0]
        minimum, maximum = 0, None
        if label == "Claude Haiku 5.5 (for prompts up to 100,000 tokens)":
            model, maximum = "claude-haiku-5-5", 100000
        elif label == "Claude Haiku 5.5 (for prompts over 100,000 tokens)":
            model, minimum = "claude-haiku-5-5", 100001
        elif label == "Claude Mythos 5.1 ([limited availability](https://support.claude.com/en/articles/14604842))":
            model = "claude-mythos-5-1"
        else:
            model = CLAUDE_NAMES.get(label)
            if model == "claude-haiku-5-5":
                raise ValueError("Haiku 5.5 prompt-band conditions are missing")
        if model is None or model not in aliases:
            continue
        rates = [mtok(c) for c in cells[1:]]
        notes = "First-party global pricing. Cache-write quote uses a 5-minute TTL; the separately priced 1-hour TTL is not shown. Cache writes and server-side tool fees are excluded from estimates."
        if model == "claude-haiku-5-5":
            notes += " Haiku 5.5 prices the entire request by full prompt length, including cached tokens: up to 100,000 versus over 100,000."
        if model == "claude-mythos-5-1":
            notes += " Limited availability; a public rate does not establish account access."
        records.append(observation("anthropic", model, rates[0], rates[4], SOURCE,
            cache_read_per_million=rates[3], cache_write_per_million=rates[1], region="global",
            min_input_tokens=minimum, max_input_tokens=maximum, pricing_notes=notes,
            **metadata(model)))
    if "claude-haiku-5-5" in aliases:
        bands = {(r["min_input_tokens"], r["max_input_tokens"]) for r in records if r["provider_model_id"] == "claude-haiku-5-5"}
        if bands != {(0, 100000), (100001, None)}:
            raise ValueError("Incomplete Haiku 5.5 prompt-band snapshot")
    require_models(records, CLAUDE_NAMES.values(), aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    return result
