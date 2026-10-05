from .common import fetch_text, markdown_tables, observation, parse_or_archive, snapshot
from .public_pricing import CLAUDE_NAMES, metadata, mtok, require_models

SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
FETCH_URL = SOURCE + ".md"
HEADER = ["model", "base input tokens", "5m cache writes", "1h cache writes", "cache hits and refreshes", "output tokens"]


def parse(body, aliases):
    records = []
    for header, cells in markdown_tables(body):
        if [c.lower() for c in header] != HEADER:
            continue
        model = CLAUDE_NAMES.get(cells[0])
        if model is None or model not in aliases:
            continue
        rates = [mtok(c) for c in cells[1:]]
        records.append(observation("anthropic", model, rates[0], rates[4], SOURCE,
            cache_read_per_million=rates[3], cache_write_per_million=rates[1], region="global",
            pricing_notes="First-party global pricing. Cache-write quote uses a 5-minute TTL; the separately priced 1-hour TTL is not shown. Cache writes and server-side tool fees are excluded from estimates.",
            **metadata(model)))
    require_models(records, CLAUDE_NAMES.values(), aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    return result
