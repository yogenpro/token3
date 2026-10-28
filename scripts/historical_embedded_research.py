"""Recover Azure's archived embedded price attributes into research only.

Visible placeholders are not zero. Preserve all regional expressions and exact
column labels, without inferring native API IDs, ISO currency or effective dates.
"""
import argparse
import json
from html.parser import HTMLParser
from pathlib import Path

from .historical_expansion import Document, markdown, document_identity
from .historical_ledger import DEFAULT_ROOT, canonical, read_asset, read_snapshot, sha
from .historical_sources import decoded, json_source
from .historical_research_files import write_report
from .historical_archive_decoding import document_text
from .historical_projection import safe_value


class NextData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.blocks, self.current = [], []

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == '__NEXT_DATA__':
            self.active = True
            self.current = []

    def handle_data(self, data):
        if self.active:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.blocks.append(''.join(self.current))
            self.active = False


def deepinfra_rows(text):
    parser = NextData()
    parser.feed(text)
    parser.close()
    if len(parser.blocks) != 1 or parser.active:
        return
    try:
        payload = json_source(parser.blocks[0].encode())
        props = payload['props']['pageProps']
    except (ValueError, TypeError, KeyError):
        return
    groups = []
    for name in ('models', '_pricingData', '_pricingDataEmbeddings'):
        values = props.get(name, [])
        if isinstance(values, list):
            groups.extend((['props', 'pageProps', name, i], model, {}) for i, model in enumerate(values))
    sections = props.get('_pricingPageData', [])
    if isinstance(sections, list):
        for si, section in enumerate(sections):
            if not isinstance(section, dict) or not isinstance(section.get('entries'), list):
                continue
            context = {k: v for k, v in section.items() if k != 'entries'}
            groups.extend((['props', 'pageProps', '_pricingPageData', si, 'entries', i], model, context) for i, model in enumerate(section['entries']))
    for pointer, model, context in groups:
        if not isinstance(model, dict) or model.get('private') or model.get('is_private') or model.get('is_public') is False:
            continue
        selected = safe_value({k: v for k, v in model.items() if k in {'model_name', 'full_name', 'name', 'owner', 'type', 'description',
            'pricing', 'max_tokens', 'context', 'deprecated', 'replaced_by', 'expected', 'quantization'} or k.startswith(('cents_per_', 'rate_per_'))})
        pricing = model.get('pricing', model)
        if not isinstance(pricing, dict):
            continue
        amounts = {k: v for k, v in pricing.items() if k.startswith(('cents_per_', 'usd_per_', 'eur_per_'))}
        if not amounts and not model.get('pricing'):
            continue
        mid = next((model[k] for k in ('model_name', 'full_name') if isinstance(model.get(k), str) and model[k]), None)
        yield dict(source_pointer=pointer, native_id=mid, model_label=mid or model.get('name'), model=selected,
            section_context=safe_value(context), amount_expression=amounts,
            identity_basis='explicit_model_identifier' if mid else 'unverified_display_label')


class EmbeddedDocument(Document):
    def handle_starttag(self, tag, attrs):
        if tag == 'table' and self.table_depth == 0:
            self.ambiguous = False
        super().handle_starttag(tag, attrs)
        values = dict(attrs)
        if not self.skip and self.cell is not None and 'data-amount' in values:
            self.cell.setdefault('embedded_prices', []).append({k: v for k, v in attrs if k.startswith('data-')})

    def handle_endtag(self, tag):
        closing_table = tag == 'table' and self.table_depth == 1
        super().handle_endtag(tag)
        if closing_table and self.tables:
            self.tables[-1]['alignment_valid'] = not self.ambiguous


def embedded_rows(text):
    parser = EmbeddedDocument()
    parser.feed(text)
    parser.close()
    for table_number, table in enumerate(parser.tables):
        if not table.get('alignment_valid') or not table['rows']:
            continue
        headers = [c['text'] for c in table['rows'][0]]
        for row_number, cells in enumerate(table['rows'][1:], 1):
            if len(headers) != len(cells):
                continue
            # Spanning cells do not establish an unambiguous model/column binding.
            if any(c['attributes'].get(key, '1') != '1' for c in cells for key in ('rowspan', 'colspan')):
                continue
            for column, cell in enumerate(cells):
                for price_number, attributes in enumerate(cell.get('embedded_prices', [])):
                    try:
                        expression = json_source(attributes['data-amount'].encode())
                    except (ValueError, TypeError, UnicodeError):
                        continue
                    if not isinstance(expression, (dict, list, int, float, str)) or isinstance(expression, bool):
                        continue
                    yield dict(table=table_number, row=row_number, column=column, price_index=price_number, headings=table['headings'],
                        headers=headers, cells=[c['text'] for c in cells], price_header=headers[column],
                        model_label=(cells[0]['text'] or None) if headers[0].strip().lower() in {'model', 'models', 'model name'} else None,
                        native_id=None, raw_amount=attributes['data-amount'],
                        amount_expression=expression, attributes=attributes)


def decoded_document_rows(text):
    from .historical_price_coverage import price_evidence
    if '<' in text[:10000] and any(tag in text[:10000].lower() for tag in ('<html', '<table', '<div', '<!doctype')):
        parser = EmbeddedDocument()
        parser.feed(text)
        parser.close()
        tables = [(i, t) for i, t in enumerate(parser.tables) if t.get('alignment_valid')]
    else:
        parsed, _ = markdown(text)
        tables = list(enumerate(parsed))
    for ti, table in tables:
        if not table['rows']:
            continue
        headers = table['rows'][0]
        for ri, cells in enumerate(table['rows'][1:], 1):
            if len(headers) != len(cells):
                continue
            if any(c['attributes'].get(key, '1') != '1' for c in headers + cells for key in ('rowspan', 'colspan')):
                continue
            clean = lambda values: [{k: v for k, v in c.items() if k in {'text', 'code'}} for c in values]
            source = dict(headers=clean(headers), cells=clean(cells), alignment_verified=True)
            probe = dict(assertion_type='historical_document_row', source_record=source, identity_scope=dict(headings=table['headings']))
            mid, basis = document_identity(headers, cells, ti, ri)
            yield dict(evidence_type='decoded_document_row', source_pointer=dict(table=ti, row=ri),
                native_id=None if basis == 'document_local' else mid, identity_basis=basis, model_label=cells[0]['text'] if cells else None,
                headings=table['headings'], source_record=source, numeric_price_candidate=price_evidence(probe) is not None,
                amount_expression={})


def capture_candidates(capture, raw):
    container = ''
    if capture['source_kind'] == 'commoncrawl_native_v4':
        from .historical_commoncrawl import payload, truncation
        if truncation(raw):
            return
        raw = payload(capture, raw)
        container = 'verified-commoncrawl-warc/'
    try:
        text, encoding = document_text(raw)
    except (UnicodeError, ValueError):
        return
    provider = capture['provider']
    records = deepinfra_rows(text) if provider == 'deepinfra' else embedded_rows(text) if provider == 'azure' else decoded_document_rows(text)
    for row in records:
        candidate = dict(provider=provider, capture_id=capture['id'], source_sha256=capture['raw']['content_sha256'],
            source_url=capture['source_url'], replay_url=capture['replay_url'], archive_capture_at=capture['archive_capture_at'],
            source_published_at=capture['source_published_at'], effective_at=None, currency=None,
            comparison_eligible=False, review_status='unreviewed_embedded_price_candidate', decoding=container + encoding, **row)
        candidate['id'] = sha(canonical(candidate))
        yield candidate


def audit(root, *, snapshot=None):
    _, rows, snapshot_sha256 = read_snapshot(root) if snapshot is None else snapshot
    candidates, captures = [], []
    encoded = {r['capture_id'] for r in rows if r['kind'] == 'coverage' and r.get('state') == 'unparsed_text_encoding'}
    for capture in rows:
        if capture['kind'] != 'capture':
            continue
        azure = capture['provider'] == 'azure' and capture['source_kind'] in {'archived_native_v2', 'arquivo_native_v3', 'commoncrawl_native_v4'} and 'azure.microsoft.com/en-us/pricing/details/' in capture['source_url']
        deepinfra = capture['provider'] == 'deepinfra' and (capture['source_kind'] == 'deepinfra_html' or
            capture['source_kind'] in {'arquivo_native_v3', 'commoncrawl_native_v4'} and '/models/list' not in capture['source_url'])
        if not azure and not deepinfra and capture['id'] not in encoded:
            continue
        recovered = list(capture_candidates(capture, read_asset(root, capture['raw'], 'sources')))
        candidates.extend(recovered)
        captures.append(dict(capture_id=capture['id'], candidate_count=len(recovered),
            state='embedded_price_candidates' if recovered else 'no_supported_embedded_price_table'))
    return dict(schema_version=1, policy='historical-embedded-price-research-v1', ledger_manifest_sha256=snapshot_sha256,
        candidates=candidates, captures=captures, limitation='Aligned Azure data-amount cells and selected public DeepInfra Next.js model/pricing records only. Brotli decoding is bounded. No inferred model versions, currency, tariff intervals, region merging or reviewed quotes; repeated page sections are not unique models or price changes.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger-dir', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.ledger_dir)
    write_report(args.output, result)
    print(json.dumps(dict(captures=len(result['captures']), candidates=len(result['candidates']))))


if __name__ == '__main__':
    main()
