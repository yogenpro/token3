"""Selected direct Mistral Standard USD quotes; full document remains native."""
import json
import re

from .common import (
    HTMLTables, fetch_text, markdown_tables, money, number, observation,
    parse_or_archive, provider_aliases, snapshot,
)
from .public_pricing import require_models

SOURCE = "https://docs.mistral.ai/inference/pricing"
IDS = ("mistral-large-4", "mistral-small-2603", "ministral-14b-2512", "ministral-8b-2512", "ministral-3b-2512", "codestral-2508")


def standard_quote(mid, rates):
    return observation("mistral", mid, rates["Input"], rates["Output"], SOURCE,
        cache_read_per_million=rates.get("Cached input"), region="default API routing",
        pricing_notes="Mistral Standard USD per million tokens; the public pricing control establishes USD/Standard. Regional, Batch, Priority, tools and non-token products are excluded. Missing cache prices and endpoint capacities remain unverified.")


def parse(body, aliases):
    aliases = provider_aliases(aliases, "mistral")
    records, seen = [], set()
    for headers, cells in markdown_tables(body):
        mid = cells[1].strip("`") if len(cells) > 1 else ""
        if mid not in aliases or mid not in IDS:
            continue
        if headers != ["Model", "API name", "Price"] or mid in seen:
            raise ValueError("Mistral pricing headers or duplicate model changed")
        seen.add(mid)
        rates = {}
        for part in cells[2].split("<br>"):
            match = re.fullmatch(r"(Input|Cached input|Output) (\$[0-9.]+) /M Tokens", part)
            if not match or match[1] in rates:
                raise ValueError("Unsupported Mistral billing expression")
            rates[match[1]] = money(match[2])
        if not {"Input", "Output"} <= rates.keys():
            raise ValueError("Incomplete Mistral token quote")
        records.append(standard_quote(mid, rates))
    require_models(records, IDS, aliases)
    return snapshot(records, body, SOURCE)


SECTIONS = {"generalist": "Generalist models", "code": "Code models"}
TOKEN_COLUMNS = ("Input", "Cached input", "Output")
PRICE_FIELDS = {"id", "direction", "priceUsd", "priceEur", "unit", "showTooltip", "label", "prefix", "tooltip"}


class LinkedPricingRows(HTMLTables):
    """Keep source links as exact row keys for the rendered price witness."""

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == "tr":
            self.links = []
        elif tag == "a" and self.cell is not None and not self.row:
            self.links.append(dict(attrs).get("href"))

    def handle_endtag(self, tag):
        if tag == "tr" and self.row and len(self.links) == 1:
            self.row[0] = self.links[0]
        super().handle_endtag(tag)


def rendered_rows(body):
    html = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    for group, title in SECTIONS.items():
        sections = re.findall(
            r'<h2\b[^>]*>' + title + r'</h2>((?:(?!<h2\b|<table\b).)*)(<table\b.*?</table>)',
            html, re.S,
        )
        if len(sections) != 1:
            raise ValueError("Mistral reviewed pricing section missing or repeated")
        controls, table = sections[0]
        active = re.findall(r'<button\b[^>]*\baria-checked="true"[^>]*>(.*?)</button>', controls, re.S)
        if [re.sub(r'<[^>]*>', '', label).strip() for label in active] != ["USD ($)", "Standard"]:
            raise ValueError("Mistral default pricing currency/tier requires review")
        parser = LinkedPricingRows()
        parser.feed(table)
        if not parser.rows or parser.rows[0] != ["Model", *TOKEN_COLUMNS]:
            raise ValueError("Mistral pricing headers changed")
        yield group, parser.rows[1:]


def serialized_models(body):
    # React Flight pushes JSON string fragments. Decode the literals only;
    # derive identity and denomination from the pricing table's model props.
    frames = re.findall(r'<script>self\.__next_f\.push\((\[1,.*?\])\)</script>', body, re.S)
    fragments = "".join(json.loads(frame)[1] for frame in frames)
    for line in fragments.splitlines():
        if '"models":[' not in line or not re.match(r'^[0-9a-f]+:\[', line):
            continue
        nodes = [json.loads(line.split(":", 1)[1])]
        while nodes:
            node = nodes.pop()
            if isinstance(node, list):
                nodes.extend(node)
            elif isinstance(node, dict):
                if set(node) == {"models"} and isinstance(node["models"], list):
                    yield from node["models"]
                else:
                    nodes.extend(node.values())


def standard_rates(model, rows):
    if model["tabs"] != []:
        raise ValueError("Mistral selected pricing acquired additional tabs")
    href = model["href"]
    if not re.fullmatch(r"/models/[a-z0-9-]+", href):
        raise ValueError("Mistral selected model link changed")
    # Match the same model path across both witnessed rendered link layouts.
    matched = [row for row in rows if row[0] in (href, "/" + href)]
    if len(matched) != 1 or len(matched[0]) != 4:
        raise ValueError("Mistral selected rendered row missing, repeated or unaligned")
    rates = {}
    for price in model["pricing"]:
        label = price["label"]
        if (set(price) != PRICE_FIELDS or label not in TOKEN_COLUMNS or label in rates
                or price["unit"] != "/M Tokens"
                or price["direction"] != ("output" if label == "Output" else "input")
                or price["showTooltip"] is not False or price["tooltip"] is not None or price["prefix"] is not None):
            raise ValueError("Unsupported Mistral billing expression")
        rates[label] = number(price["priceUsd"])
    if not {"Input", "Output"} <= rates.keys():
        raise ValueError("Incomplete Mistral token quote")
    visible = {label: None if cell == "-" else money(cell) for label, cell in zip(TOKEN_COLUMNS, matched[0][1:])}
    if visible != {label: rates.get(label) for label in TOKEN_COLUMNS}:
        raise ValueError("Mistral serialized rates disagree with rendered USD Standard prices")
    return rates


def parse_html(body, aliases):
    aliases = provider_aliases(aliases, "mistral")
    expected = set(aliases) & set(IDS)
    tables = dict(rendered_rows(body))
    records, seen = [], set()
    for model in serialized_models(body):
        ids = model["modelIds"]
        if not isinstance(ids, list) or any(not isinstance(mid, str) for mid in ids):
            raise ValueError("Mistral model IDs changed format")
        matched = expected.intersection(ids)
        if not matched:
            continue
        if len(matched) != 1 or len(set(ids)) != len(ids) or matched & seen or model["catalogGroup"] not in tables:
            raise ValueError("Mistral reviewed model binding is ambiguous")
        mid = matched.pop()
        rates = standard_rates(model, tables[model["catalogGroup"]])
        records.append(standard_quote(mid, rates))
        seen.add(mid)
    require_models(records, IDS, aliases)
    return snapshot(records, body, SOURCE)


def collect(aliases):
    body = fetch_text(SOURCE, headers={"Accept": "text/html"})
    result = parse_or_archive(body, SOURCE, parse_html, aliases)
    result.source_urls = [SOURCE]
    return result
