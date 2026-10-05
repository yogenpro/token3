from .common import fetch_text, markdown_tables, money, observation, parse_or_archive, snapshot
from .public_pricing import metadata, require_models, section

SOURCE = "https://developers.openai.com/api/docs/pricing"
FETCH_URL = SOURCE + ".md"
ROWS = {"gpt-5.4 (<272K context length)": "gpt-5.4", "gpt-5.4": "gpt-5.4", "gpt-5.4-mini": "gpt-5.4-mini"}
API_IDS = {"gpt-5.4": "gpt-5.4-2026-03-05", "gpt-5.4-mini": "gpt-5.4-mini-2026-03-17"}
HEADER = ["Model", "Short context input", "Short context cached input", "Short context cache writes", "Short context output", "Long context input", "Long context cached input", "Long context cache writes", "Long context output"]


def parse(body, aliases):
    records = []
    standard = section(body, "Standard pricing data", 3)
    for header, cells in markdown_tables(standard):
        model = ROWS.get(cells[0])
        if model is None or API_IDS[model] not in aliases:
            continue
        if header != HEADER:
            raise ValueError("OpenAI standard pricing table changed")
        short = [money(c, optional=True) for c in cells[1:5]]
        long = [money(c, optional=True) for c in cells[5:9]]
        if short[0] is None or short[3] is None:
            raise ValueError("OpenAI input/output rate is missing")
        if long == [None] * 4:
            if model == "gpt-5.4":
                raise ValueError("Known GPT-5.4 long-prompt rates are missing; refusing to extrapolate short pricing")
            bands = [(short, 0, None, "standard")]
        else:
            if long[0] is None or long[3] is None or "Short context: ≤272K input tokens. Long context: >272K input tokens." not in body:
                raise ValueError("OpenAI long-context rates or boundary are ambiguous")
            bands = [(short, 0, 272000, "short prompt"), (long, 272001, None, "long prompt")]
        for rates, minimum, maximum, variant in bands:
            records.append(observation("openai", API_IDS[model], rates[0], rates[3], SOURCE,
                cache_read_per_million=rates[1], cache_write_per_million=rates[2], region="global",
                min_input_tokens=minimum, max_input_tokens=maximum, variant=variant,
                pricing_notes="Standard text-token pricing. Reasoning tokens count as output. Tool fees and cache writes are excluded from estimates. Prompt bands count the full input, including cached tokens.",
                **metadata(model)))
    require_models(records, API_IDS.values(), aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse, aliases)
    result.source_urls = [FETCH_URL]
    return result
