"""Collection-only sources: public fixture excerpts, never production backfills."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from providers.common import Collection
from providers.expanded import INVENTORY_PROVIDERS, _listing, _oracle, _scaleway, _snowflake_pdf
from scripts.catalog_inventory import canonical, normalize_inventory
from scripts.collect import PROVIDERS, run

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/expanded-pricing.json').read_text())


def collection(provider, payload=None, fallback=None):
    payload = copy.deepcopy(payload if payload is not None else FIXTURES[provider])
    body = canonical(payload)
    return Collection([], INVENTORY_PROVIDERS[provider].SOURCE, hashlib.sha256(body.encode()).hexdigest(),
                      source_payload=body, source_kind='documentation' if payload['adapter'] == 'documents' else 'api',
                      inventory_only=True, fallback_reason=fallback)


def normalize(provider, payload=None):
    result = collection(provider, payload)
    return normalize_inventory(provider, result.source_payload, result.source_kind)


class ExpandedInventoryTests(unittest.TestCase):
    def test_all_fifteen_public_sources_are_inventory_only(self):
        self.assertEqual(len(INVENTORY_PROVIDERS), 15)
        self.assertEqual(len(PROVIDERS), 26)
        for provider in INVENTORY_PROVIDERS:
            with self.subTest(provider=provider):
                document, fingerprint = normalize(provider)
                self.assertTrue(document['records'])
                self.assertEqual(len(fingerprint), 64)
                self.assertTrue(all(r['provider'] == provider and not r['comparison_eligible'] for r in document['records']))

    def test_gateway_native_per_token_prices_are_not_assumed_per_million(self):
        for provider in ('openrouter', 'vercel'):
            document, _ = normalize(provider)
            priced = [r for row in document['records'] for r in row['rates']]
            self.assertTrue(any('input token' == r['unit'] for r in priced))
            self.assertFalse(any('1M' in (r['unit'] or '') for r in priced))

    def test_openrouter_dynamic_sentinel_is_unknown_not_free(self):
        payload = copy.deepcopy(FIXTURES['openrouter'])
        payload['catalog']['data'] = [{'id': 'openrouter/auto', 'pricing': {'prompt': '-1', 'completion': '-1'}}]
        row = normalize('openrouter', payload)[0]['records'][0]
        self.assertEqual(row['rates'], [])
        self.assertEqual(row['billing']['state'], 'dynamic_price')
        self.assertEqual(row['billing']['rules']['prompt'], '-1')
        payload['catalog']['data'][0]['pricing']['prompt'] = '-2'
        with self.assertRaises(ValueError): normalize('openrouter', payload)

    def test_vercel_regions_bands_modalities_and_unknown_components_are_retained(self):
        payload = copy.deepcopy(FIXTURES['vercel'])
        pricing = payload['catalog']['data'][0]['pricing']
        pricing.update(input_tiers=[{'min': 200000, 'cost': '0.000002'}], regional={'us': {'input': '0.0000022'}},
                       image_dimension_quality_pricing=[{'quality': 'high', 'cost': '0.08'}])
        rows = normalize('vercel', payload)[0]['records']
        row = next(r for r in rows if r['native_id'] == payload['catalog']['data'][0]['id'])
        self.assertEqual(row['billing']['rules'], pricing)
        self.assertFalse(row['comparison_eligible'])

    def test_huggingface_routes_keep_upstream_identity_and_native_units(self):
        rows = normalize('huggingface')[0]['records']
        routes = [r for r in rows if r['kind'] == 'provider_route']
        self.assertTrue(routes)
        self.assertTrue(all(r['scope']['upstream_provider'] for r in routes))
        self.assertTrue(any(r['unit'] == '1M input tokens' for row in routes for r in row['rates']))
        self.assertTrue(any('compute' in n.lower() for n in normalize('huggingface')[0]['billing_notes']))

    def test_huggingface_missing_route_price_and_free_flag_do_not_invent_zero(self):
        payload = copy.deepcopy(FIXTURES['huggingface'])
        route = payload['catalog']['data'][0]['providers'][0]
        route.pop('pricing', None)
        route['is_free'] = True
        rows = normalize('huggingface', payload)[0]['records']
        row = next(r for r in rows if r['native_id'] == payload['catalog']['data'][0]['id'] and r['scope']['upstream_provider'] == route['provider'])
        self.assertEqual(row['rates'], [])
        self.assertEqual(row['billing']['state'], 'source_native_or_unpriced')

    def test_performance_metrics_do_not_create_price_history_noise(self):
        for provider in ('huggingface', 'nebius', 'ovhcloud'):
            payload = copy.deepcopy(FIXTURES[provider])
            before = normalize(provider, payload)[1]
            if provider == 'huggingface':
                for row in payload['catalog']['data']:
                    for route in row['providers']:
                        route.update(first_token_latency_ms=123456, throughput=98765)
            elif provider == 'nebius':
                for row in payload['catalog']:
                    row['quality'] = 123456
                    for flavor in row['flavors']: flavor['tokens_per_second'] = 98765
            else:
                for row in payload['catalog']:
                    row['metadata']['benchmark_results'] = [{'score': 123456}]
                    row['metadata'].setdefault('usage_information', {})['avg_throughtput'] = 98765
            self.assertEqual(before, normalize(provider, payload)[1])

    def test_nebius_flavor_and_region_context_is_not_discarded(self):
        rows = normalize('nebius')[0]['records']
        self.assertTrue(all('region' in r['scope'] and 'flavor' in r['scope'] for r in rows))
        self.assertTrue(all('1M' in rate['unit'] for row in rows for rate in row['rates']))

    def test_ovh_currency_absence_remains_unknown_not_usd_or_eur(self):
        rows = normalize('ovhcloud')[0]['records']
        self.assertTrue(any(row['billing']['native_rates'] for row in rows))
        for row in rows:
            self.assertEqual(row['rates'], [])
            for value in row['billing']['native_rates']: self.assertIsNone(value['currency'])
        payload = copy.deepcopy(FIXTURES['ovhcloud'])
        payload['catalog'][0]['metadata']['usage_information']['pricing'][0]['price'] = -1
        with self.assertRaises(ValueError): normalize('ovhcloud', payload)

    def test_oracle_preserves_native_metric_and_price_model(self):
        rows = normalize('oracle')[0]['records']
        self.assertTrue(all(r['scope']['price_model'] and r['rates'][0]['currency'] == 'USD' for r in rows))
        self.assertTrue(all(r['rates'][0]['unit'] == r['billing']['unit'] for r in rows))

    def test_scaleway_money_unit_size_and_unpriced_skus_are_explicit(self):
        rows = normalize('scaleway')[0]['records']
        self.assertTrue(all(r['rates'][0]['currency'] == 'EUR' for r in rows))
        self.assertTrue(all(r['rates'][0]['unit'] == r['billing']['unit_of_measure']['unit'] for r in rows))
        payload = copy.deepcopy(FIXTURES['scaleway'])
        payload['catalog']['products'][0].update(price=None, unit_of_measure=None)
        unknown = next(r for r in normalize('scaleway', payload)[0]['records'] if r['native_id'] == payload['catalog']['products'][0]['sku'])
        self.assertEqual(unknown['rates'], [])
        payload['catalog']['products'][0]['price'] = 'unreviewed malformed money'
        with self.assertRaises(ValueError): normalize('scaleway', payload)

    def test_nonfinite_negative_and_boolean_amounts_fail_closed(self):
        for provider in ('openrouter', 'vercel', 'huggingface', 'oracle', 'scaleway'):
            for value in (True, '-2', 'NaN', 'Infinity'):
                with self.subTest(provider=provider, value=value):
                    payload = copy.deepcopy(FIXTURES[provider])
                    if provider in ('openrouter', 'vercel'):
                        payload['catalog']['data'][0]['pricing']['prompt' if provider == 'openrouter' else 'input'] = value
                    elif provider == 'huggingface': payload['catalog']['data'][0]['providers'][0]['pricing']['input'] = value
                    elif provider == 'oracle': payload['catalog']['items'][0]['currencyCodeLocalizations'][0]['prices'][0]['value'] = value
                    else: payload['catalog']['products'][0]['price']['retail_price']['units'] = value
                    with self.assertRaises((ValueError, ArithmeticError)): normalize(provider, payload)

    def test_api_private_rows_and_adapter_identity_mismatches_are_rejected(self):
        for provider in ('openrouter', 'vercel', 'huggingface', 'nebius', 'ovhcloud'):
            payload = copy.deepcopy(FIXTURES[provider])
            rows = payload['catalog'] if isinstance(payload['catalog'], list) else payload['catalog']['data']
            rows[0]['private'] = True
            with self.assertRaises(ValueError): normalize(provider, payload)
        payload = copy.deepcopy(FIXTURES['vercel'])
        with self.assertRaises(ValueError): normalize('openrouter', payload)

    def test_mdx_regions_and_markdown_headings_survive_mixed_tables(self):
        body = '# Model prices\n<Tabs>\n<Tab title="Singapore">\n## Text\n<table><tr><th>Model</th><th>Price per 1M tokens</th></tr><tr><td>qwen-test</td><td>$0.20</td></tr></table>\n</Tab>\n<Tab title="Mainland China">\n| Model | Price CNY per 1M tokens |\n|---|---|\n| qwen-test | 0.30 |\n</Tab>\n</Tabs>'
        payload = {'format': 'token3.inventory-sources.v1', 'adapter': 'documents', 'documents': [{'source_url': 'https://example.com/prices', 'body': body}]}
        rows = normalize('alibaba', payload)[0]['records']
        self.assertEqual(len(rows), 2)
        self.assertEqual({tuple(r['scope']['tabs']) for r in rows}, {('Singapore',), ('Mainland China',)})
        self.assertTrue(all('Model prices' in r['scope']['headings'] for r in rows))

    def test_doc_credit_and_currency_amount_changes_keep_row_identity(self):
        for header, first, second in [('DBU per 1M tokens', '2.00', '3.00'), ('Price EUR / 1M tokens', '0.20€', '0.30€'), ('Price USD per 1M tokens', '$0.20', '$0.30')]:
            payload = {'format': 'token3.inventory-sources.v1', 'adapter': 'documents', 'documents': [{'source_url': 'https://example.com/prices', 'body': '| Model | ' + header + ' |\n|---|---|\n| test-model | ' + first + ' |\n'}]}
            before, fingerprint = normalize('databricks', payload)
            payload['documents'][0]['body'] = payload['documents'][0]['body'].replace(first, second)
            after, changed = normalize('databricks', payload)
            self.assertEqual(before['records'][0]['id'], after['records'][0]['id'])
            self.assertNotEqual(fingerprint, changed)

    def test_document_only_native_dbu_and_credit_cells_are_not_guessed_as_usd(self):
        rows = normalize('databricks')[0]['records']
        self.assertTrue(rows)
        self.assertTrue(all(not r['comparison_eligible'] for r in rows))
        self.assertTrue(all(not r['rates'] for r in rows))

    def test_pdf_provenance_hash_does_not_make_unchanged_page_text_a_price_change(self):
        payload = copy.deepcopy(FIXTURES['snowflake'])
        payload['pdf_document'] = {'source_url': 'https://example.com/prices.pdf', 'response_sha256': 'a' * 64,
            'extraction': 'layout; alignment unreviewed', 'pages': [{'page': 1, 'text': 'Cortex AI credits: native billing table'}]}
        before = normalize('snowflake', payload)[1]
        payload['pdf_document']['response_sha256'] = 'b' * 64
        self.assertEqual(before, normalize('snowflake', payload)[1])


class ExpandedRequestTests(unittest.TestCase):
    def test_public_model_list_checks_complete_pagination_and_total(self):
        base = {'data': [{'id': 'test'}], 'links': {'next': None}, 'total_count': 1}
        with patch('providers.expanded.fetch_text', return_value=json.dumps(base)):
            self.assertEqual(_listing('https://example.com/models')['total_count'], 1)
        for change in ({'links': {'next': 'https://evil.com'}}, {'total_count': 2}, {'has_more': True}, {'data': []}):
            with patch('providers.expanded.fetch_text', return_value=json.dumps(dict(base, **change))):
                with self.assertRaises(ValueError): _listing('https://example.com/models')

    def test_scaleway_paginates_all_products_but_selects_only_ai_categories(self):
        items = copy.deepcopy(FIXTURES['scaleway']['catalog']['products'])
        unrelated = dict(items[0], sku='domain/test', product_category='Domains and DNS')
        pages = [{'products': [items[0], unrelated], 'total_count': 3}, {'products': [items[1]], 'total_count': 3}]
        with patch('providers.expanded.fetch_text', side_effect=list(map(json.dumps, pages))) as fetch:
            payload, urls = _scaleway('https://example.com/products?page_size=2')
        self.assertEqual(len(payload['products']), 2)
        self.assertEqual(len(urls), 2)
        self.assertIn('page=2', fetch.call_args.args[0])
        for final in ({'products': [items[0]], 'total_count': 3}, {'products': [items[1]], 'total_count': 4}, {'products': [], 'total_count': 3}):
            with patch('providers.expanded.fetch_text', side_effect=[json.dumps(pages[0]), json.dumps(final)]):
                with self.assertRaises(ValueError): _scaleway('https://example.com/products')

    def test_oracle_selects_generative_ai_and_rejects_partial_lists(self):
        items = copy.deepcopy(FIXTURES['oracle']['catalog']['items'])
        items.append(dict(items[0], displayName='OCI Database'))
        with patch('providers.expanded.fetch_text', return_value=json.dumps({'items': items})):
            self.assertEqual(len(_oracle('https://example.com/prices')['items']), len(items) - 1)
        with patch('providers.expanded.fetch_text', return_value=json.dumps({'items': items, 'hasMore': True})):
            with self.assertRaises(ValueError): _oracle('https://example.com/prices')

    def test_snowflake_optional_pdf_failure_records_a_limited_source_not_model_rates(self):
        collector = INVENTORY_PROVIDERS['snowflake']
        body = FIXTURES['snowflake']['documents'][0]['body']
        with patch('providers.expanded.fetch_text', return_value=body), patch('providers.expanded._snowflake_pdf', side_effect=RuntimeError('HTTP 403')):
            result = collector.collect()
        self.assertTrue(result.inventory_only)
        self.assertIn('billing-guide coverage only', result.fallback_reason)
        self.assertEqual(result.records, [])
        self.assertIn('model rates unavailable', result.source_payload)

    def test_pdf_reader_preserves_native_page_text_and_exact_bytes_hash(self):
        page = SimpleNamespace(extract_text=lambda **kw: 'Table 6 Cortex AI: 0.36 AI Credits per million tokens')
        with patch('providers.expanded.fetch_bytes', return_value=b'%PDF-fixture'), patch('pypdf.PdfReader', return_value=SimpleNamespace(is_encrypted=False, pages=[page])):
            result = _snowflake_pdf('https://example.com/prices.pdf')
        self.assertEqual(result['response_sha256'], hashlib.sha256(b'%PDF-fixture').hexdigest())
        self.assertIn('AI Credits', result['pages'][0]['text'])
        with patch('providers.expanded.fetch_bytes', return_value=b'<html>denied</html>'):
            with self.assertRaises(ValueError): _snowflake_pdf('https://example.com/prices.pdf')


class InventoryOnlyRetentionTests(unittest.TestCase):
    def test_inventory_only_bootstrap_success_and_unchanged_retry_do_not_create_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(PROVIDERS, {'openrouter': SimpleNamespace(collect=lambda aliases: collection('openrouter'), SOURCE=INVENTORY_PROVIDERS['openrouter'].SOURCE)}):
                self.assertEqual(run(root, ['openrouter'], strict=True), 0)
                first = (root / 'inventory_history.jsonl').read_bytes()
                catalog = (root / 'provider_catalogs/openrouter.json').read_bytes()
                self.assertEqual(run(root, ['openrouter'], strict=True), 0)
            self.assertEqual(first, (root / 'inventory_history.jsonl').read_bytes())
            self.assertEqual(catalog, (root / 'provider_catalogs/openrouter.json').read_bytes())
            self.assertFalse((root / 'offerings.json').exists())
            status = json.loads((root / 'status.json').read_text())['providers'][0]
            self.assertEqual(status['offering_count'], 0)
            self.assertEqual(status['collection_scope'], 'inventory_only')
            self.assertEqual(json.loads((root / 'provider_inventory.json').read_text())['providers'][0]['curated_parser_state'], 'not_applicable')

    def test_invalid_inventory_cannot_clobber_last_good_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            collector = SimpleNamespace(collect=lambda aliases: collection('openrouter'), SOURCE=INVENTORY_PROVIDERS['openrouter'].SOURCE)
            with patch.dict(PROVIDERS, {'openrouter': collector}):
                self.assertEqual(run(root, ['openrouter'], strict=True), 0)
                before = (root / 'provider_catalogs/openrouter.json').read_bytes()
                collector.collect = lambda aliases: collection('openrouter', dict(FIXTURES['openrouter'], catalog={'data': []}))
                self.assertEqual(run(root, ['openrouter'], strict=True), 1)
            self.assertEqual(before, (root / 'provider_catalogs/openrouter.json').read_bytes())
            self.assertEqual(json.loads((root / 'status.json').read_text())['providers'][0]['state'], 'error')

    def test_snowflake_pdf_outage_preserves_previously_complete_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = copy.deepcopy(FIXTURES['snowflake'])
            payload['pdf_document'] = {'source_url': 'https://example.com/prices.pdf', 'response_sha256': 'a' * 64,
                'extraction': 'layout; alignment unreviewed', 'pages': [{'page': 1, 'text': 'Cortex AI native prices'}]}
            collector = SimpleNamespace(collect=lambda aliases: collection('snowflake', payload), SOURCE=INVENTORY_PROVIDERS['snowflake'].SOURCE)
            with patch.dict(PROVIDERS, {'snowflake': collector}):
                self.assertEqual(run(root, ['snowflake'], strict=True), 0)
                before = (root / 'provider_catalogs/snowflake.json').read_bytes()
                collector.collect = lambda aliases: collection('snowflake', fallback='Consumption PDF unavailable')
                self.assertEqual(run(root, ['snowflake'], strict=True), 1)
            self.assertEqual(before, (root / 'provider_catalogs/snowflake.json').read_bytes())

    def test_inventory_only_source_cannot_publish_reviewed_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            result = collection('openrouter')
            result.records = [{'provider': 'openrouter'}]
            with patch.dict(PROVIDERS, {'openrouter': SimpleNamespace(collect=lambda aliases: result, SOURCE=result.source_url)}):
                self.assertEqual(run(Path(directory), ['openrouter'], strict=True), 1)
            self.assertFalse((Path(directory) / 'provider_catalogs/openrouter.json').exists())


if __name__ == '__main__':
    unittest.main()
