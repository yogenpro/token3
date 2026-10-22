import re

from .common import fetch_text, money, observation, parse_or_archive, provider_aliases, snapshot
from .public_pricing import metadata, require_models, section

SOURCE = "https://developers.openai.com/api/docs/pricing"
FETCH_URL = SOURCE + ".md"
ROWS = {"gpt-5.4 (<272K context length)": "gpt-5.4", "gpt-5.4": "gpt-5.4", "gpt-5.4-mini": "gpt-5.4-mini"}
API_IDS = {"gpt-5.4": "gpt-5.4-2026-03-05", "gpt-5.4-mini": "gpt-5.4-mini-2026-03-17",
           "gpt-6-astra": "gpt-6-astra", "gpt-6.1-sol": "gpt-6.1-sol", "gpt-6-luna": "gpt-6-luna", "gpt-6-sol": "gpt-6-sol"}
ROWS.update({model: model for model in API_IDS if model.startswith("gpt-6")})
LONG_CONTEXT_MODELS = frozenset(("gpt-5.4", "gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna", "gpt-6-sol"))
HEADER = ["Model", "Short context input", "Short context cached input", "Short context cache writes", "Short context output", "Long context input", "Long context cached input", "Long context cache writes", "Long context output"]
RETENTION_HEADER = ["Model", "Short context input", "Short context output", "Short context cached input", "Short context 30m write", "Short context 12h write", "Long context input", "Long context output", "Long context cached input", "Long context 30m write", "Long context 12h write"]
UNIFORM_HEADER = ["Model", "Input", "Output", "Cached input"]
SCHEMAS = (frozenset(HEADER), frozenset(RETENTION_HEADER), frozenset(UNIFORM_HEADER))


def _tracked_rows(standard, aliases):
    # Unlike the generic Markdown reader, do not silently omit a malformed
    # tracked row or let a second valid row hide an incomplete/conflicting one.
    header, seen = None, set()
    for line in standard.splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line[1:-1].split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells):
            continue
        if header is None:
            header = cells
            continue
        model = ROWS.get(cells[0])
        if model is None or API_IDS[model] not in aliases:
            continue
        schema = frozenset(header)
        if header[0] != "Model" or len(header) != len(schema) or schema not in SCHEMAS:
            raise ValueError("OpenAI standard pricing table changed")
        if len(cells) != len(header):
            raise ValueError("OpenAI tracked pricing row is incomplete")
        if model in seen:
            raise ValueError("Duplicate OpenAI model pricing row: {}".format(model))
        seen.add(model)
        yield model, schema, dict(zip(header, cells))


def parse(body, aliases):
    aliases = provider_aliases(aliases, "openai")
    records = []
    standard = section(body, "Standard pricing data", 3)
    # A denominator in Batch or another later section cannot establish Standard's.
    preamble = body.split("### Standard pricing data", 1)[0]
    unit_pattern = r"(?m)^[ \t]*Prices per[^\r\n]*"
    units = re.findall(unit_pattern, preamble)[-1:] + re.findall(unit_pattern, standard)
    if not units or any(unit.strip() != "Prices per 1M tokens." for unit in units):
        raise ValueError("OpenAI pricing token denominator is missing or changed")
    for model, schema, row in _tracked_rows(standard, aliases):
        if schema == frozenset(UNIFORM_HEADER):
            short = [money(row["Input"], optional=True), money(row["Cached input"], optional=True), None, money(row["Output"], optional=True)]
            long = [None] * 4
        else:
            # The user explicitly reviewed current 30m writes. 12h is a distinct
            # native-only scope, never a fallback or the cheapest-column choice.
            write = "30m write" if schema == frozenset(RETENTION_HEADER) else "cache writes"
            def rates(prefix):
                return [money(row[prefix + " " + field], optional=True) for field in ("input", "cached input", write, "output")]
            short, long = rates("Short context"), rates("Long context")
        if short[0] is None or short[3] is None:
            raise ValueError("OpenAI input/output rate is missing")
        if long == [None] * 4:
            if model in LONG_CONTEXT_MODELS:
                raise ValueError("Known {} long-prompt rates are missing; refusing to extrapolate short pricing".format(model))
            bands = [(short, 0, None, "standard")]
        else:
            if long[0] is None or long[3] is None or "Short context: ≤272K input tokens. Long context: >272K input tokens." not in body:
                raise ValueError("OpenAI long-context rates or boundary are ambiguous")
            bands = [(short, 0, 272000, "short prompt"), (long, 272001, None, "long prompt")]
        for values, minimum, maximum, variant in bands:
            notes = "Standard text-token pricing. Reasoning tokens count as output. Tool fees and cache writes are excluded from estimates. Prompt bands count the full input, including cached tokens."
            if schema == frozenset(RETENTION_HEADER) and values[2] is not None:
                notes += " Current cache-write component: 30-minute retention only; 12-hour writes remain native-only. Historical unqualified write observations do not establish retention."
            records.append(observation("openai", API_IDS[model], values[0], values[3], SOURCE,
                cache_read_per_million=values[1], cache_write_per_million=values[2], region="global",
                min_input_tokens=minimum, max_input_tokens=maximum, variant=variant,
                pricing_notes=notes, **metadata(model)))
    require_models(records, API_IDS.values(), aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    return result
