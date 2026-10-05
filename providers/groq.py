import re
from .common import HTMLTables, fetch_text, markdown_tables, number, observation, parse_or_archive, snapshot

SOURCE = "https://console.groq.com/docs/models"
FETCH_URL = SOURCE + ".md"
IDS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant")


def parse(body, aliases):
    parser = HTMLTables()
    parser.feed(body)
    records = []
    for cells in parser.rows:
        if len(cells) < 5:
            continue
        model_id = next((mid for mid in IDS if mid in aliases and mid in cells[0].split()), None)
        if not model_id:
            continue
        if "Contact" in cells[2]:
            continue  # Negotiated prices are explicitly out of scope.
        input_rate = re.search(r"\$([\d.]+)\s*input", cells[2], re.I)
        output_rate = re.search(r"\$([\d.]+)\s*output", cells[2], re.I)
        if not input_rate or not output_rate:
            raise ValueError("Groq input/output price layout changed for {}".format(model_id))
        context = cells[4].replace(",", "").strip()
        if not context.isdigit():
            raise ValueError("Groq context window layout changed")
        records.append(observation("groq", model_id, number(input_rate.group(1)), number(output_rate.group(1)),
                                   SOURCE, context_window=int(context)))
    return snapshot(records, body, SOURCE, authoritative=False)


def parse_markdown(body, aliases):
    records = []
    for header, cells in markdown_tables(body):
        required = ("MODEL ID", "PRICE PER 1M TOKENS", "CONTEXT WINDOW (TOKENS)")
        if any(field not in header for field in required):
            continue
        row = dict(zip(header, cells))
        # The official model-detail link provides an exact ID, not a substring
        # match that could merge safeguard or other model variants.
        link = re.search(r"\]\(/docs/model/([^)]+)\)", row["MODEL ID"])
        model_id = link.group(1) if link else row["MODEL ID"].strip("`")
        if model_id not in IDS or model_id not in aliases:
            continue
        prices = row["PRICE PER 1M TOKENS"]
        if "Contact" in prices:
            continue
        input_rate = re.search(r"\$([\d.]+)\s*input", prices, re.I)
        output_rate = re.search(r"\$([\d.]+)\s*output", prices, re.I)
        if not input_rate or not output_rate:
            raise ValueError("Groq Markdown input/output token prices changed")
        context = row["CONTEXT WINDOW (TOKENS)"].replace(",", "").strip()
        if not context.isdigit():
            raise ValueError("Groq Markdown context window changed")
        records.append(observation("groq", model_id, number(input_rate.group(1)), number(output_rate.group(1)),
                                   SOURCE, context_window=int(context)))
    return snapshot(records, body, SOURCE)


def collect(aliases):
    result = parse_or_archive(fetch_text(FETCH_URL), SOURCE, parse_markdown, aliases)
    result.source_urls = [FETCH_URL]
    result.source_kind = "documentation"
    return result
