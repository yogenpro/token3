"""Native records for explicitly scoped public documents and price feeds."""
import re
from html.parser import HTMLParser

from .catalog_inventory import entry, rate


class VisibleDocument(HTMLParser):
    """Read visible source text; scripts and markup never execute."""
    HIDDEN = frozenset(("script", "style", "template", "svg", "noscript", "iframe"))
    VOID = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"))

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden, self.parts = [], []

    def handle_starttag(self, tag, attrs):
        if tag in self.HIDDEN:
            self.hidden.append(tag)

    def handle_endtag(self, tag):
        if self.hidden and tag == self.hidden[-1]:
            self.hidden.pop()

    def handle_data(self, value):
        if not self.hidden and value.strip():
            self.parts.append(value.strip())


def document_page(provider, body, url):
    if body.lstrip().startswith("<"):
        if re.search(r"<title>\s*(?:Page Not Found|Access Denied|Just a moment|404)\b", body, re.I):
            raise ValueError("Public document returned an error page")
        parser = VisibleDocument()
        parser.feed(body)
        visible = "\n".join(parser.parts)
    else:
        # Keep normalized surrounding prose. Tables have separate native rows;
        # SDK/request/response examples are not tariffs or observations. This
        # is a text projection, not retention/publication of the raw response.
        parts, fence = [], False
        for raw in body.lstrip('\ufeff').splitlines():
            line = re.sub(r"^(?:> ?)+", "", raw.strip())
            if line.startswith(('```', '~~~')):
                fence = not fence
                continue
            if fence or not line or line.startswith('|'):
                continue
            line = re.sub(r"^#{1,6}\s+", "", line)
            line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)
            line = line.replace('**', '').replace('`', '').replace('\\$', '$')
            parts.append(line)
        visible = '\n'.join(parts)
    if not visible or len(visible.encode()) > 128 * 1024:
        raise ValueError("Public document is empty or exceeds the bounded page limit")
    if re.search(r"^(?:# )?(?:Page Not Found|Access Denied|Just a moment|404)\b", visible, re.I):
        raise ValueError("Public document returned an error page")
    return entry(provider, url, "document_page", "Public billing/model document",
        {"source_url": url},
        {"text": visible, "interpretation": "Unaligned public document text. No model identity, rate, currency, unit or availability inferred."},
        {"table_alignment_verified": False})


def unquote_tabs(body):
    """Restore explicit quoted Markdown tab headings without changing rates."""
    lines = []
    for raw in body.splitlines():
        line = re.sub(r"^> ?", "", raw)
        match = re.fullmatch(r"\[tab\] (.+)", line)
        lines.append("### " + match[1] if match else line)
    return "\n".join(lines)


def public_feed(provider, catalog, documents=()):
    if not isinstance(catalog, dict) or catalog.get("object") != "list":
        raise ValueError("Public price feed must declare a list")
    if any(catalog.get(key) for key in ("has_more", "next", "next_page", "nextPageToken", "next_page_token")):
        raise ValueError("Public price feed pagination requires review")
    if catalog.get("links", {}).get("next"):
        raise ValueError("Public price feed pagination requires review")
    if provider == "cerebras":
        witnesses = [d.get("body", "") for d in documents if d.get("source_url") ==
                     "https://inference-docs.cerebras.ai/api-reference/models/public-models.md"]
        if len(witnesses) != 1 or "Pricing per token in USD." not in witnesses[0]:
            raise ValueError("Cerebras default-feed currency/unit witness requires review")
        if catalog.get("currency") not in (None, "USD"):
            raise ValueError("Cerebras default-feed currency changed")
    rows = catalog.get("data")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Public price feed must contain nonempty model data")
    for key in ("total", "total_count"):
        if key in catalog and catalog[key] != len(rows):
            raise ValueError("Public price feed total does not match the listing")
    records, seen = [], set()
    for product, items in (("inference", rows), ("training", catalog.get("training", []))):
        if not isinstance(items, list):
            raise ValueError("Public product prices must be a list")
        for model in items:
            if not isinstance(model, dict):
                raise ValueError("Public model row must be an object")
            mid = model.get("id" if provider == "cerebras" else "model")
            if not isinstance(mid, str) or not mid or (product, mid) in seen:
                raise ValueError("Public model ID is missing or duplicated")
            seen.add((product, mid))
            if any(model.get(k) for k in ("private", "is_private")) or model.get("is_public") is False:
                raise ValueError("Private model data is outside the public feed scope")
            rates = []
            if provider == "cerebras":
                pricing = model.get("pricing")
                if not isinstance(pricing, dict) or not {"prompt", "completion"} <= pricing.keys():
                    raise ValueError("Cerebras pricing is incomplete")
                if any(value not in (None, "USD") for value in (model.get("currency"), pricing.get("currency"))):
                    raise ValueError("Cerebras default-feed currency changed")
                for key in ("prompt", "completion"):
                    rates.append(rate(key, pricing[key], "token", "USD", source_field="pricing." + key))
                limits = model.get("limits") or {}
                metadata = {"source_model_id": mid, "context_length": limits.get("max_context_length"),
                            "max_output_tokens": limits.get("max_completion_tokens"),
                            "quantization": model.get("quantization"), "model_name": model.get("name")}
            elif provider == "castform":
                keys = ("input_per_1m_tokens", "output_per_1m_tokens") if product == "inference" else ("train_per_1m_tokens",)
                for key in keys:
                    if key in model:
                        rates.append(rate(key, model[key], "1M tokens", model.get("currency"), source_field=key))
                if product == "inference" and len(rates) != 2:
                    raise ValueError("Castform inference prices are incomplete")
                metadata = {"source_model_id": mid, "context_length": model.get("context_length"),
                            "model_name": model.get("display_name", mid)}
            else:
                raise ValueError("Unsupported public pricing feed")
            records.append(entry(provider, mid, "model", model.get("name", model.get("display_name", mid)),
                {"billing_product": product}, {"rules": model, "interpretation": "Exact public price-feed fields; products and units remain separate."},
                metadata, rates))
    return records
