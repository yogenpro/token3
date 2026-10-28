"""Historical-native-v2: explicit public profiles, native catalogs and document evidence.

No amount normalization, alias inference, currency inference, current-price claims
or absence-based retirement. V1 extraction stays unchanged for its existing rows.
"""
import base64
import hashlib
import io
import json
import re
from collections import OrderedDict
from datetime import timezone
from html.parser import HTMLParser
from functools import lru_cache
from urllib.parse import urlsplit

from .historical_profiles import DOCUMENT_KINDS, PROFILE, archive_query, normalized, source_spec
from .historical_sources import archive_time, decoded, json_source, timestamp

EXTRACTOR = "historical-native-v2"
MAX_TEXT = 8 * 1024 * 1024
TEXT_CHUNK = 16384
PDF_EXTRACTOR = "pypdf-6.19.0"
PDF_CACHE_BYTES = 64 * 1024 * 1024
PDF_CACHE_ENTRIES = 128
_pdf_cache = OrderedDict()


def pdf_pages(content):
    """Reuse immutable page text only after each capture's witness verification.

    Nothing is persisted. Exact source SHA-256, versioned historical extractor
    and pinned PDF parser identify entries; byte and entry caps bound memory.
    """
    import pypdf
    if "pypdf-" + pypdf.__version__ != PDF_EXTRACTOR:
        raise ValueError("Historical PDF parser version differs from its recorded extractor")
    key = (hashlib.sha256(content).digest(), EXTRACTOR, PDF_EXTRACTOR)
    if key in _pdf_cache:
        _pdf_cache.move_to_end(key)
        return _pdf_cache[key][0]
    reader = pypdf.PdfReader(io.BytesIO(content), strict=True)
    pages = None if reader.is_encrypted or len(reader.pages) > 100 else tuple(page.extract_text() or "" for page in reader.pages)
    size = sum(len(text.encode()) for text in pages) if pages is not None else 0
    if size > MAX_TEXT:
        raise ValueError("Historical PDF extraction exceeds text cap")
    if size <= PDF_CACHE_BYTES:
        while _pdf_cache and (len(_pdf_cache) >= PDF_CACHE_ENTRIES or sum(item[1] for item in _pdf_cache.values()) + size > PDF_CACHE_BYTES):
            _pdf_cache.popitem(last=False)
        if PDF_CACHE_ENTRIES > 0:
            _pdf_cache[key] = (pages, size)
    return pages


@lru_cache(maxsize=64)
def index_entries(raw):
    return frozenset((r[0], r[1], r[4]) for r in json_source(raw)[1:])


def validate_check(row, context):
    keys = {"id", "kind", "capture_id", "provider", "profile", "provenance", "source_url", "target_url", "checked_at",
            "state", "http_status", "transport_exit_code", "archive_capture_at", "archive_digest", "index_capture_id", "comparison_eligible"}
    states = {"transport_failed", "http_failed", "digest_mismatch", "redirect_denied", "budget_deferred", "extractor_rejected", "oversized_or_empty_body", "invalid_transport", "oversized_headers"}
    if (set(row) != keys or row["profile"] != PROFILE or row["kind"] != "coverage" or row["capture_id"] is not None
            or row["provenance"] != "historical_discovery_v2" or row["state"] not in states or row["comparison_eligible"] is not False):
        raise ValueError("Invalid expansion discovery check")
    checked = timestamp(row["checked_at"])
    source_spec(row["target_url"], row["provider"])
    if row["http_status"] is not None and (type(row["http_status"]) is not int or not 100 <= row["http_status"] <= 599):
        raise ValueError("Invalid discovery HTTP status")
    if row["transport_exit_code"] is not None and type(row["transport_exit_code"]) is not int:
        raise ValueError("Invalid transport status")
    if row["state"] == "budget_deferred" and (row["http_status"] is not None or row["transport_exit_code"] is not None):
        raise ValueError("Deferred lookup cannot assert an HTTP response")
    if row["state"] == "transport_failed" and row["http_status"] is not None:
        raise ValueError("Transport failure cannot assert a provider HTTP response")
    if row["archive_capture_at"] is not None:
        stamp = timestamp(row["archive_capture_at"]).astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        if timestamp(row["archive_capture_at"]) > checked or row["source_url"] != "https://web.archive.org/web/{}id_/{}".format(stamp, row["target_url"]):
            raise ValueError("Invalid failed replay target/time")
        witness = context.get(row["index_capture_id"])
        if witness is None or witness[0]["provider"] != row["provider"] or witness[0]["source_kind"] != "archive_index_v2":
            raise ValueError("Failed replay lacks a retained index witness")
        if (stamp, row["target_url"], row["archive_digest"]) not in index_entries(witness[1]):
            raise ValueError("Failed replay index entry differs")
    else:
        if row["archive_digest"] is not None or row["index_capture_id"] is not None:
            raise ValueError("Lookup failure cannot invent a capture")
        if row["source_url"].startswith("https://web.archive.org/cdx/"):
            if archive_query(row["source_url"], row["provider"]) != row["target_url"]:
                raise ValueError("Failed index query target differs")
        elif row["source_url"] != row["target_url"] or not source_spec(row["target_url"], row["provider"]).get("allow_current_document"):
            raise ValueError("Unsupported failed current-document lookup")


def same_target(a, b, provider):
    source_spec(a, provider)
    source_spec(b, provider)
    na, nb = normalized(a), normalized(b)
    # CDX canonicalizes www and terminal slash. Both literal source URLs must still be allowlisted.
    return (na[0].removeprefix("www."), na[1:]) == (nb[0].removeprefix("www."), nb[1:])


def validate_capture(capture):
    if capture['source_kind'] in {'commoncrawl_index_v4', 'commoncrawl_native_v4'}:
        from .historical_commoncrawl import validate_capture as validate_commoncrawl
        return validate_commoncrawl(capture)
    if capture['source_kind'] in {'arquivo_index_v3', 'arquivo_native_v3'}:
        from .historical_arquivo import validate_capture as validate_arquivo
        return validate_arquivo(capture)
    provider, kind, scope = capture["provider"], capture["source_kind"], capture["request_scope"]
    if kind not in DOCUMENT_KINDS or scope.get("profile") != PROFILE:
        raise ValueError("Unsupported expansion source kind/profile")
    retrieved = timestamp(capture["retrieved_at"])
    if capture["source_published_at"] is not None:
        raise ValueError("Expansion adapters do not infer document publication dates")
    if kind == "archive_index_v2":
        target = archive_query(capture["source_url"], provider)
        if scope != dict(profile=PROFILE, target_url=target):
            raise ValueError("Expansion index scope differs")
    else:
        spec = source_spec(capture["source_url"], provider)
    if kind == "archived_native_v2":
        if set(scope) != {"profile", "index_capture_id"}:
            raise ValueError("Expansion replay needs its exact index witness")
        stamp = timestamp(capture["archive_capture_at"]).astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        if (timestamp(capture["archive_capture_at"]) > retrieved
                or capture["replay_url"] != "https://web.archive.org/web/{}id_/{}".format(stamp, capture["source_url"])
                or not isinstance(capture["archive_digest"], str) or not re.fullmatch(r"[A-Z2-7]{32}", capture["archive_digest"])):
            raise ValueError("Expansion archive target/time/digest differs")
    else:
        if any(capture[k] is not None for k in ("archive_capture_at", "archive_digest", "replay_url")):
            raise ValueError("Non-replay cannot assert an archive timestamp")
        if kind == "public_document_v2":
            if set(scope) != {"profile", "final_url"} or not spec.get("allow_current_document"):
                raise ValueError("Only selected retrospective public documents may be fetched live")
            if not source_spec(scope["final_url"], provider).get("allow_current_document"):
                raise ValueError("Unapproved retrospective document redirect")


class Document(HTMLParser):
    """Preserve table context plus visible narrative; never evaluate page scripts."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.headings, self.heading, self.level = [], None, 0
        self.text, self.blocks, self.tables = [], [], []
        self.table, self.row, self.cell, self.table_context = None, None, None, []
        self.table_depth, self.ambiguous = 0, False
        self.code = 0

    def flush(self):
        text = " ".join(self.text).strip()
        if text:
            self.blocks.append(dict(headings=list(self.headings), text=text))
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if self.skip:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.flush()
            self.heading, self.level = [], int(tag[1])
        if tag == "table":
            self.table_depth += 1
            if self.table is not None:
                self.ambiguous = True
            else:
                self.table, self.table_context = [], list(self.headings)
        if tag == "tr" and self.table is not None:
            if self.row is not None:
                self.ambiguous = True
            self.row = []
        if tag in ("td", "th") and self.row is not None:
            if self.cell is not None:
                self.ambiguous = True
            self.cell = dict(text=[], code=[], links=[], attributes=dict(attrs))
        if tag == "code":
            self.code += 1
        if tag == "a" and self.cell is not None and dict(attrs).get("href"):
            self.cell["links"].append(dict(attrs)["href"])

    def handle_data(self, text):
        if self.skip or not text.strip():
            return
        value = " ".join(text.split())
        if self.heading is not None:
            self.heading.append(value)
        else:
            self.text.append(value)
        if self.cell is not None:
            self.cell["text"].append(value)
            if self.code:
                self.cell["code"].append(value)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        if self.skip:
            return
        if re.fullmatch(r"h[1-6]", tag) and self.heading is not None:
            self.headings = self.headings[:self.level - 1] + [" ".join(self.heading)]
            self.heading = None
        if tag == "code":
            self.code = max(0, self.code - 1)
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.cell["text"] = " ".join(self.cell["text"])
            self.row.append(self.cell)
            self.cell = None
        if tag == "tr" and self.row is not None:
            if self.cell is not None:
                self.ambiguous = True
            if self.table is not None:
                self.table.append(self.row)
            self.row = None
        if tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0 and self.table is not None:
                self.tables.append(dict(headings=self.table_context, rows=self.table))
                self.table = None
            self.flush()
        if tag in ("p", "li", "div", "section", "article", "pre", "body"):
            self.flush()


class RoleDocument(Document):
    """Read explicitly opted-in DIV tables using their declared ARIA structure."""
    def __init__(self):
        super().__init__()
        self.div_tags = []

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            tag = {"table": "table", "rowgroup": "tbody", "row": "tr", "cell": "td",
                   "columnheader": "th", "rowheader": "th"}.get(dict(attrs).get("role"), tag)
            self.div_tags.append(tag)
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "div":
            if not self.div_tags:
                self.ambiguous = True
                return
            tag = self.div_tags.pop()
        super().handle_endtag(tag)


def markdown(text):
    tables, blocks, headings, current = [], [], [], None
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        heading = re.match(r"^(#{1,6})\s+(.+)", line) if not fenced else None
        if heading:
            headings = headings[:len(heading[1]) - 1] + [heading[2]]
        if line.strip():
            blocks.append(dict(headings=list(headings), text=line, line=number, fenced_code=fenced))
        if not fenced and line.strip().startswith("|") and line.strip().endswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip()[1:-1])]
            if all(re.fullmatch(r":?-+:?", c) for c in cells):
                continue
            if current is None:
                current = dict(headings=list(headings), rows=[], line=number)
                tables.append(current)
            current["rows"].append([dict(text=c, code=re.findall(r"`([^`]+)`", c), links=[], attributes={}) for c in cells])
        else:
            current = None
    return tables, blocks


def document_identity(headers, cells, ti, ri):
    names = [c["text"].strip().lower() for c in headers]
    exact = {"model id", "api model name", "api model id", "deprecated model", "retired model", "sku", "part number", "meter id"}
    candidates = [i for i, name in enumerate(names) if name in exact]
    if len(candidates) == 1 and candidates[0] < len(cells):
        value = cells[candidates[0]]["text"].strip().strip("`")
        if re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
            return value, "explicit_identifier_column"
    if cells and names and names[0] in ("model", "model name", "model / system"):
        codes = cells[0].get("code", [])
        if len(codes) == 1 and re.fullmatch(r"[A-Za-z0-9_./:-]+", codes[0]):
            return codes[0], "explicit_code_identifier"
    return "table/{}/row/{}".format(ti, ri), "document_local"


def extract(capture, raw, context):
    validate_capture(capture)
    provider, kind = capture["provider"], capture["source_kind"]
    assertions = []

    def emit(native_id, assertion_type, pointer, value, scope):
        assertions.append(dict(kind="assertion", provider=provider, capture_id=capture["id"], extractor=EXTRACTOR,
            assertion_type=assertion_type, native_id=native_id, identity_scope=scope, source_pointer=pointer,
            source_record=value, source_reported_effective_at=None, review_status="unreviewed_historical", comparison_eligible=False))

    if kind == 'commoncrawl_index_v4':
        from .historical_commoncrawl import index_entries as commoncrawl_entries
        rows = commoncrawl_entries(capture, raw)
        coverage = dict(state='index_only', returned_entries=len(rows),
                        scope='selected successful source URL entries in one retained Common Crawl CDX block; not a full archive query')
    elif kind == 'arquivo_index_v3':
        from .historical_arquivo import verify_index
        rows = verify_index(capture, raw)
        coverage = dict(state='index_only', returned_entries=len(rows), entry_cap=5001, cap_reached=len(rows) >= 5001,
                        scope='one exact Arquivo.pt source URL; indexed is not replayed or priced')
    elif kind == "archive_index_v2":
        data = json_source(raw)
        if not isinstance(data, list) or (data and data[0] != ["timestamp", "original", "mimetype", "statuscode", "digest"]):
            raise ValueError("Invalid expansion archive index")
        target = capture["request_scope"]["target_url"]
        for row in data[1:]:
            if not isinstance(row, list) or len(row) != 5 or row[3] != "200" or not re.fullmatch(r"[A-Z2-7]{32}", row[4]):
                raise ValueError("Malformed expansion archive entry")
            archive_time(row[0])
            if not same_target(row[1], target, provider):
                raise ValueError("Expansion archive index escaped its exact URL scope")
        coverage = dict(state="index_only", returned_entries=max(0, len(data) - 1), entry_cap=5001,
                        cap_reached=len(data) - 1 >= 5001, scope="one exact source URL; indexed is not replayed or priced")
    else:
        if kind == 'commoncrawl_native_v4':
            from .historical_commoncrawl import verify_witness, truncation
            original_raw = raw
            raw = verify_witness(capture, raw, context)
            partial = truncation(original_raw)
            if partial:
                return [], dict(kind='coverage', capture_id=capture['id'], provider=provider, extractor=EXTRACTOR,
                    state='truncated_archived_response', truncation_reason=partial, assertion_count=0, comparison_eligible=False,
                    scope='exact truncated WARC retained and digest-verified; incomplete source is not parsed as a complete pricing document')
        elif kind == 'arquivo_native_v3':
            from .historical_arquivo import verify_witness
            verify_witness(capture, raw, context)
        elif kind == "archived_native_v2":
            index = context.get(capture["request_scope"]["index_capture_id"])
            if index is None or index[0]["provider"] != provider or index[0]["source_kind"] != "archive_index_v2":
                raise ValueError("Expansion capture lacks its provider's retained index")
            if not same_target(index[0]["request_scope"]["target_url"], capture["source_url"], provider):
                raise ValueError("Expansion source and index target differ")
            digest = base64.b32encode(hashlib.sha1(raw).digest()).decode()
            stamp = timestamp(capture["archive_capture_at"]).astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
            if digest != capture["archive_digest"] or (stamp, capture["source_url"], digest) not in index_entries(index[1]):
                raise ValueError("Expansion replay digest/index witness differs")
        spec = source_spec(capture["source_url"], provider)
        content = decoded(raw)
        if spec['format'] == 'deepinfra':
            payload = json_source(raw)
            if not isinstance(payload, list) or not payload:
                raise ValueError('Historical DeepInfra API lacks its public model list')
            ids = set()
            for i, model in enumerate(payload):
                if not isinstance(model, dict) or model.get('private') or model.get('is_private') or model.get('is_public') is False:
                    raise ValueError('Malformed/private historical DeepInfra model')
                mid = model.get('model_name')
                if not isinstance(mid, str) or not mid or mid in ids:
                    raise ValueError('Invalid/duplicate DeepInfra model ID')
                ids.add(mid)
                emit(mid, 'deepinfra_model', [i], model, {})
            coverage = dict(state='native_inventory_evidence', returned_entries=len(payload), scope='returned public archive model list; no absence-based retirement')
        elif spec["format"] == "oracle":
            payload = json_source(raw)
            items = payload.get('items') if isinstance(payload, dict) else None
            if not isinstance(items, list):
                raise ValueError('Oracle historical source lacks its items array')
            ids = set()
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    raise ValueError('Malformed historical Oracle product')
                if 'generative ai' not in str(item.get('serviceCategory', '')).lower():
                    continue
                mid = item.get('partNumber')
                if not isinstance(mid, str) or not mid or mid in ids or item.get('private'):
                    raise ValueError('Invalid/duplicate historical Oracle part number')
                ids.add(mid)
                emit(mid, 'historical_oracle_sku', ['items', i], item,
                     dict(source_url=capture['source_url'], identity_basis='explicit_part_number'))
            coverage = dict(state='native_inventory_evidence', returned_entries=len(items), selected_entries=len(ids),
                            scope='archived Oracle Generative AI service categories only; exact metrics/currencies retained; no absence-based retirement or catalog completeness claim')
        elif spec["format"] == "nebius":
            payload = json_source(raw)
            if not isinstance(payload, list):
                raise ValueError('Historical Nebius public models response is not an array')
            ids = set()
            for i, model in enumerate(payload):
                if not isinstance(model, dict) or not isinstance(model.get('flavors'), list) or model.get('private'):
                    raise ValueError('Malformed/private historical Nebius model')
                for fi, flavor in enumerate(model['flavors']):
                    if not isinstance(flavor, dict) or flavor.get('private'):
                        raise ValueError('Malformed/private historical Nebius flavor')
                    mid = flavor.get('model_id')
                    identity = (mid, flavor.get('label'), json.dumps(flavor.get('regions'), sort_keys=True), flavor.get('quantization'))
                    if not isinstance(mid, str) or not mid or identity in ids:
                        raise ValueError('Invalid/duplicate historical Nebius flavor')
                    ids.add(identity)
                    emit(mid, 'historical_nebius_flavor', [i, 'flavors', fi], dict(model=model, flavor=flavor),
                         dict(source_url=capture['source_url'], identity_basis='explicit_model_flavor', flavor=flavor.get('label'), regions=flavor.get('regions')))
            coverage = dict(state='native_inventory_evidence', returned_entries=len(payload),
                            scope='archived public model/flavor response; exact IDs, regions and per-million-token fields; currency/effective intervals not inferred')
        elif spec["format"] == "models":
            try:
                payload = json_source(raw)
            except (ValueError, UnicodeError):
                payload = None
            items = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload, dict) else None
            links = payload.get("links") if isinstance(payload, dict) else None
            incomplete = isinstance(payload, dict) and (payload.get("has_more") or payload.get("nextPageToken") or
                (links is not None and (not isinstance(links, dict) or links.get("next"))))
            if isinstance(payload, dict):
                for field in ("total_count", "total"):
                    if field in payload and isinstance(items, list) and payload[field] != len(items):
                        incomplete = True
            if not isinstance(items, list) or not items or incomplete:
                coverage = dict(state="unparsed_or_incomplete_catalog", scope="exact body retained; no complete catalog asserted")
            else:
                ids = set()
                for i, model in enumerate(items):
                    if not isinstance(model, dict):
                        raise ValueError("Malformed historical model object")
                    if model.get("private") or model.get("is_private") or model.get("is_public") is False or model.get("visibility") == "private":
                        raise ValueError("Private historical model source rejected")
                    mid = model.get("id")
                    if not isinstance(mid, str) or not mid or mid in ids:
                        raise ValueError("Duplicate or missing historical model identifier")
                    ids.add(mid)
                    pointer = [i] if isinstance(payload, list) else ["data", i]
                    if provider == "huggingface":
                        routes = model.get("providers")
                        if not isinstance(routes, list) or not routes:
                            raise ValueError("Historical Hugging Face routes are incomplete")
                        seen_routes = set()
                        for j, route in enumerate(routes):
                            if not isinstance(route, dict):
                                raise ValueError("Malformed historical provider route")
                            if route.get("private") or route.get("is_private") or route.get("is_public") is False or route.get("visibility") == "private":
                                raise ValueError("Private historical provider route rejected")
                            upstream = route.get("provider")
                            if not isinstance(upstream, str) or not upstream or upstream in seen_routes:
                                raise ValueError("Ambiguous historical provider route")
                            seen_routes.add(upstream)
                            emit(mid, "historical_provider_route", pointer + ["providers", j], dict(model={k:v for k,v in model.items() if k != "providers"}, route=route),
                                 dict(upstream_provider=upstream))
                    else:
                        emit(mid, "historical_native_model", pointer, model, {})
                coverage = dict(state="complete_returned_snapshot", models=len(items), scope="returned public catalog only; no supplier/availability equivalence")
        elif spec["format"] == "pdf":
            if not content.startswith(b"%PDF-"):
                coverage = dict(state="unsupported_pdf_body", scope="body retained; no PDF rates asserted")
            else:
                pages = pdf_pages(content)
                if pages is None:
                    coverage = dict(state="unparsed_pdf_limit", scope="encrypted or over 100 pages; no partial extraction asserted")
                else:
                    for i, text in enumerate(pages):
                        emit("page/" + str(i + 1), "historical_pdf_page", dict(page=i + 1),
                             dict(text=text, extraction=PDF_EXTRACTOR, alignment_verified=False), dict(source_url=capture["source_url"], page=i + 1))
                    coverage = dict(state="pdf_text_only", pages=len(pages), scope="unaligned page text; not model-to-rate mappings or credits-to-currency conversion")
        else:
            try:
                text = content.decode("utf-8-sig")
            except UnicodeError:
                text = None
            if text is None:
                coverage = dict(state="unparsed_text_encoding", scope="exact bytes retained; encoding not guessed")
            else:
                if re.search(r"<(?:!doctype|html|body|main|div|table|script)\b", text[:10000], re.I):
                    parser = RoleDocument() if spec.get("html_table_roles") else Document()
                    parser.feed(text)
                    parser.close()
                    parser.flush()
                    ambiguous = parser.ambiguous or parser.table is not None or parser.row is not None or parser.cell is not None or bool(getattr(parser, "div_tags", []))
                    tables, blocks = ([] if ambiguous else parser.tables), parser.blocks
                else:
                    tables, blocks = markdown(text)
                    ambiguous = False
                if sum(len(b["text"].encode()) for b in blocks) > MAX_TEXT:
                    raise ValueError("Historical visible text exceeds cap")
                for ti, table in enumerate(tables):
                    section = spec.get("section_text_contains")
                    if section and section.casefold() not in " ".join(table["headings"]).casefold() and not any(
                            section.casefold() in cell["text"].casefold() for row in table["rows"] for cell in row):
                        continue
                    rows = table["rows"]
                    if not rows:
                        continue
                    for ri, cells in enumerate(rows[1:], 1):
                        mid, basis = document_identity(rows[0], cells, ti, ri)
                        unit_context = {}
                        if spec.get("html_table_roles"):
                            units = [b["text"] for b in blocks if re.fullmatch(r"Prices shown are per 1 million tokens\.", b["text"])]
                            if len(set(units)) == 1:
                                unit_context["unit_context"] = units[0]
                        emit(mid, "historical_document_row", dict(table=ti, row=ri),
                             dict(headers=rows[0], cells=cells, alignment_verified=len(cells) == len(rows[0]), **unit_context),
                             dict(source_url=capture["source_url"], headings=table["headings"], identity_basis=basis))
                # Keep complete context without producing hundreds of boilerplate
                # assertions for adjacent DIV/P/LI fragments under the same heading.
                grouped = []
                for bi, block in enumerate(blocks):
                    section = spec.get("section_text_contains")
                    if section and section.casefold() not in (" ".join(block["headings"]) + " " + block["text"]).casefold():
                        continue
                    scope = (block["headings"], block.get("fenced_code", False))
                    if grouped and (grouped[-1]["headings"], grouped[-1]["fenced_code"]) == scope:
                        grouped[-1]["text"] += "\n" + block["text"]
                        grouped[-1]["block_end"] = bi
                    else:
                        grouped.append(dict(headings=block["headings"], fenced_code=block.get("fenced_code", False),
                                            text=block["text"], block_start=bi, block_end=bi))
                for block in grouped:
                    for start in range(0, len(block["text"]), TEXT_CHUNK):
                        chunk = dict(block, text=block["text"][start:start + TEXT_CHUNK])
                        emit("text/{}/{}".format(block["block_start"], start), "historical_document_text",
                             dict(block_start=block["block_start"], block_end=block["block_end"], offset=start), chunk,
                             dict(source_url=capture["source_url"], headings=block["headings"], identity_basis="document_local"))
                coverage = dict(state="document_text_only_ambiguous_tables" if ambiguous else "document_evidence",
                                tables=len(tables), text_blocks=len(blocks), scope="visible unreviewed document evidence; conditions retained, no normalized quotes")
    coverage.update(kind="coverage", capture_id=capture["id"], provider=provider, extractor=EXTRACTOR,
                    assertion_count=len(assertions), comparison_eligible=False)
    return assertions, coverage
