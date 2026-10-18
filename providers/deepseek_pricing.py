"""Validate DeepSeek's transposed, time-of-use table without creating reviewed quotes.

The original document rows remain intact. Explicit model-column evidence supports
additional native model records, not canonical aliases or calculator eligibility.
"""
import re
from decimal import Decimal
from html.parser import HTMLParser


def clean(value):
    return " ".join(value.replace("\u200b", "").split())


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables, self.table, self.row, self.cell = [], None, None, None
        self.all_text, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "header", "footer"):
            self.skip += 1
        if self.skip:
            return
        if tag == "table":
            if self.table is not None:
                raise ValueError("Nested DeepSeek price table")
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            attrs = dict(attrs)
            spans = [int(attrs.get(k, "1")) for k in ("rowspan", "colspan")]
            if any(not 1 <= n <= 32 for n in spans):
                raise ValueError("Unsupported DeepSeek table span")
            self.cell = [[], *spans]
        elif tag == "br":
            self.handle_data(" ")

    def handle_data(self, data):
        if self.skip:
            return
        self.all_text.append(data)
        if self.cell is not None:
            self.cell[0].append(data)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer") and self.skip:
            self.skip -= 1
            return
        if self.skip:
            return
        if tag in ("td", "th") and self.cell is not None:
            self.row.append((clean(" ".join(self.cell[0])), *self.cell[1:]))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def expand(rows):
    grid, occupied = [], {}
    if len(rows) > 100:
        raise ValueError("DeepSeek price table exceeds row limit")
    for y, cells in enumerate(rows):
        x = 0
        for value, height, width in cells:
            while (y, x) in occupied:
                x += 1
            for dy in range(height):
                for dx in range(width):
                    key = y + dy, x + dx
                    if key in occupied or key[1] >= 32:
                        raise ValueError("Overlapping DeepSeek table cells")
                    occupied[key] = value
            x += width
        width = max((col + 1 for row, col in occupied if row == y), default=0)
        grid.append([occupied.get((y, col), "") for col in range(width)])
    if any(row >= len(rows) for row, _ in occupied):
        raise ValueError("Incomplete DeepSeek row span")
    return grid


def parse_models(body):
    parser = Tables()
    parser.feed(body)
    candidates = [expand(t) for t in parser.tables if t and t[0] and t[0][0][0] == "MODEL"]
    if len(candidates) != 1:
        raise ValueError("DeepSeek source lacks one complete model pricing table")
    rows = candidates[0]
    header = rows[0]
    start = next((i for i, value in enumerate(header) if value != "MODEL"), len(header))
    ids = [re.sub(r"\s*\(\d+\)$", "", v) for v in header[start:]]
    if not {"deepseek-flash", "deepseek-v4-pro"}.issubset(ids) or len(set(ids)) != len(ids) or any(not re.fullmatch(r"deepseek-[a-z0-9-]+", v) for v in ids):
        raise ValueError("DeepSeek source has ambiguous model columns")
    if any(len(row) != len(header) for row in rows):
        raise ValueError("DeepSeek model table is incomplete or unaligned")
    prose = clean(" ".join(parser.all_text))
    schedule = re.search(r"Peak hours are .+?holidays in full\.", prose)
    if not schedule or "units of per 1M tokens" not in prose:
        raise ValueError("DeepSeek token denominator or time-of-use schedule is missing")
    versions = [r for r in rows if r[0] == "MODEL VERSION"]
    contexts = [r for r in rows if r[0] == "CONTEXT LENGTH"]
    outputs = [r for r in rows if r[0] == "MAX OUTPUT"]
    if any(len(rs) != 1 or any(not value for value in rs[0][start:]) for rs in (versions, contexts, outputs)):
        raise ValueError("DeepSeek model version/capacity evidence is incomplete")
    model_rates = {mid: [] for mid in ids}
    for row in rows[1:]:
        labels = row[:start]
        if "PRICING" not in labels[0]:
            continue
        if len(labels) != 3 or labels[2] not in ("PEAK", "OFF-PEAK"):
            raise ValueError("Unsupported DeepSeek price period")
        dimensions = {"1M INPUT TOKENS (CACHE HIT)": ("cache_read", "1M cached input tokens"),
                      "1M INPUT TOKENS (CACHE MISS)": ("input", "1M input tokens"),
                      "1M OUTPUT TOKENS": ("output", "1M output tokens")}
        if labels[1] not in dimensions:
            raise ValueError("Unsupported DeepSeek price dimension")
        dimension, unit = dimensions[labels[1]]
        for i, mid in enumerate(ids):
            value = row[start + i]
            if not re.fullmatch(r"\$\d+(?:\.\d+)?", value):
                raise ValueError("DeepSeek price is not an explicit dollar amount")
            model_rates[mid].append(dict(dimension=dimension, amount=format(Decimal(value[1:]), "f"),
                                        currency="USD", unit=unit,
                                        conditions=dict(time_of_use=labels[2], peak_schedule=schedule[0],
                                                        model_version=versions[0][start + i])))
    expected = {(d, p) for d in ("input", "output", "cache_read") for p in ("PEAK", "OFF-PEAK")}
    result = []
    for i, mid in enumerate(ids):
        rates = model_rates[mid]
        if len(rates) != 6 or {(r["dimension"], r["conditions"]["time_of_use"]) for r in rates} != expected:
            raise ValueError("DeepSeek source lacks complete peak/off-peak model prices")
        result.append(dict(native_id=mid, version=versions[0][start + i], context=contexts[0][start + i],
                           output=outputs[0][start + i], rates=rates, schedule=schedule[0]))
    return result
