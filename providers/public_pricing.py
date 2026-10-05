"""Small, fail-closed helpers for official public pricing documents.

Model IDs/capacities are reviewed, not inferred by fuzzy name matching. Prices
always come from the fetched document; never from this metadata registry.
"""
import re
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from .common import money, number

# Capacity references: the publisher's official model reference pages. Cloud
# endpoint capacities are left unverified unless separately documented.
MODEL_METADATA = {
    "gpt-5.4": (1050000, 128000),
    "gpt-5.4-mini": (400000, 128000),
    "claude-sonnet-4-6": (1000000, 128000),
    "claude-opus-4-6": (1000000, 128000),
    "claude-haiku-4-5-20251001": (200000, 64000),
}
CLAUDE_NAMES = {
    "Claude Sonnet 4.6": "claude-sonnet-4-6",
    "Claude Opus 4.6": "claude-opus-4-6",
    "Claude Haiku 4.5": "claude-haiku-4-5-20251001",
}
GEMINI_NAMES = {
    "Gemini 3.8 Flash": "gemini-3.8-flash",
    "Gemini 3.5 Flash-Lite": "gemini-3.5-flash-lite",
}


def today():
    return datetime.now(timezone.utc).date()


def metadata(model_id, cloud=False):
    context, output = MODEL_METADATA.get(model_id, (None, None))
    return dict(context_window=None if cloud else context,
                max_output_tokens=None if cloud else output)


def require_models(records, expected, aliases):
    expected = {model for model in expected if model in aliases}
    actual = {record["provider_model_id"] for record in records}
    if expected - actual:
        raise ValueError("Tracked model(s) missing from pricing source: {}".format(", ".join(sorted(expected - actual))))
    return records


def unique_records(records):
    """Only identical repeats may be collapsed; conflicting quotes are errors."""
    result = {}
    for record in records:
        key = tuple(record.get(k) for k in ("provider_model_id", "service_tier", "region", "min_input_tokens", "max_input_tokens"))
        if key in result and result[key] != record:
            raise ValueError("Conflicting duplicate price rows: {}".format(key))
        result[key] = record
    return list(result.values())


def section(text, title, level=2):
    pattern = r"^{} {}\s*$".format("#" * level, re.escape(title))
    match = re.search(pattern, text, re.M)
    if not match:
        raise ValueError("Missing document section: {}".format(title))
    rest = text[match.end():]
    end = re.search(r"^#{1," + str(level) + r"} ", rest, re.M)
    return rest[:end.start()] if end else rest


def mtok(cell):
    # Footnote markers are not part of the numeric value.
    cell = re.sub(r"<sup>.*?</sup>", "", cell).strip()
    return money(re.sub(r"\s*/\s*MTok$", "", cell))


def dated_rate(cell, as_of=None, storage=False):
    """Read a current token rate, not a future announced rate or cache storage.

    The two reviewed Gemini models have single text-token rates, optionally
    followed by an explicit introductory/future date schedule. Storage charges
    use tokens/hour and are never interpreted as token cache-read/write rates.
    """
    as_of = as_of or today()
    cell = cell.replace("\\$", "$").strip()
    if storage:
        cell = re.split(r"\$[0-9.]+\s*/\s*1,000,000 tokens per hour", cell)[0].strip()
    schedule = re.fullmatch(
        r"\$([0-9.]+) through ([A-Za-z]+ \d{1,2}, \d{4})\.\s*"
        r"\$([0-9.]+) starting ([A-Za-z]+ \d{1,2}, \d{4})\.", cell)
    if schedule:
        first, through, following, start = schedule.groups()
        end_date = datetime.strptime(through, "%B %d, %Y").date()
        start_date = datetime.strptime(start, "%B %d, %Y").date()
        if (start_date - end_date).days != 1:
            raise ValueError("Noncontiguous introductory pricing dates")
        return number(first if as_of <= end_date else following)
    # Parenthesized modalities explicitly apply to the same single quoted rate.
    plain = re.fullmatch(r"\$([0-9.]+)(?: \(text / image / video / audio\))?", cell)
    if not plain:
        raise ValueError("Unsupported token rate/schedule: {}".format(cell))
    return number(plain.group(1))


def gemini_vertex_label(label, as_of=None):
    as_of = as_of or today()
    labels = {
        "Gemini 3.8 Flash* through December 31, 2026": ("gemini-3.8-flash", None, date(2026, 12, 31)),
        "Gemini 3.8 Flash Starting January 1, 2027": ("gemini-3.8-flash", date(2027, 1, 1), None),
        "Gemini 3.8 Flash": ("gemini-3.8-flash", None, None),
        "Gemini 3.5 Flash-Lite": ("gemini-3.5-flash-lite", None, None),
    }
    entry = labels.get(label)
    if entry is None:
        return None
    model, start, end = entry
    return model if (start is None or as_of >= start) and (end is None or as_of <= end) else None


class PricingHTML(HTMLParser):
    """Keep HTML tables and their actual tab labels (region / service tier).

    Prices from different regions must not be guessed from DOM order. Tab IDs
    are only references: semantic labels come from the buttons themselves.
    Google uses explicit blank cells for continued model/type rows.
    """
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tabs = {}
        self.stack = []
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("role") == "tab" and attrs.get("id") and attrs.get("track-metadata-eventdetail"):
            self.tabs[attrs["id"]] = attrs["track-metadata-eventdetail"]
        label = self.tabs.get(attrs.get("aria-labelledby")) if attrs.get("role") == "tabpanel" else None
        if tag not in self.VOID:
            self.stack.append((tag, label))
        if tag == "table":
            if self.table is not None:
                raise ValueError("Nested pricing tables are unsupported")
            self.table = dict(labels=[value for _, value in self.stack if value], rows=[])
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("th", "td") and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.table["rows"].append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            self.tables.append(self.table)
            self.table = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
