"""Explicit source review, native units and last-good retention regressions."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.comparison_expansion import PROVIDERS
from providers.expanded import INVENTORY_PROVIDERS
from providers.reviewed_inventory import reviewed_quotes
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import apply_snapshot, read_history, run
from scripts.normalize import catalog, normalize

FIXTURES = Path(__file__).parent / 'fixtures/provider-comparisons'
TIME = '2026-10-26T00:00:00Z'
HASH = 'a' * 64


def fixture(provider):
    return json.loads((FIXTURES / (provider + '.json')).read_text())


class ProviderComparisonTests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()

    def quotes(self, provider, payload=None):
        return reviewed_quotes(provider, payload or fixture(provider), self.aliases, INVENTORY_PROVIDERS[provider].SOURCE)

    def test_each_requested_source_has_separately_bound_normalizable_quotes(self):
        self.assertEqual(len(PROVIDERS), 14)
        expected = {'openrouter': 3, 'alibaba': 1, 'huggingface': 5, 'snowflake': 3, 'cloudflare': 8,
                    'databricks': 4, 'oracle': 2, 'nebius': 5, 'xai': 2, 'zai': 3,
                    'ovhcloud': 2, 'scaleway': 1, 'minimax': 4, 'deepseek': 4}
        for provider in sorted(PROVIDERS):
            with self.subTest(provider=provider):
                rows = self.quotes(provider)
                self.assertEqual(len(rows), expected[provider])
                normalized = [normalize(r, self.aliases, TIME, HASH) for r in rows]
                self.assertEqual(len({o['id'] for o, p in normalized}), len(rows))
                self.assertEqual({r['provider_model_id'] for r in rows}, set(self.aliases.for_provider(provider)))
                with self.assertRaises(ValueError):
                    reviewed_quotes(provider, fixture(provider), {}, INVENTORY_PROVIDERS[provider].SOURCE)

    def test_native_records_are_still_comparison_ineligible(self):
        for provider in sorted(PROVIDERS):
            with self.subTest(provider=provider):
                payload = fixture(provider)
                doc, _ = normalize_inventory(provider, json.dumps(payload), 'documentation')
                self.assertTrue(doc['records'])
                self.assertTrue(all(r['comparison_eligible'] is False for r in doc['records']))

    def test_legacy_aliases_are_preserved_without_leaking_new_source_ids(self):
        self.assertIn('openai/gpt-oss-120b', self.aliases.for_provider('deepinfra'))
        self.assertNotIn('GPT-OSS-120B', self.aliases.for_provider('deepinfra'))
        self.assertNotIn('gpt-oss-120b', self.aliases.for_provider('deepinfra'))
        self.assertNotIn('MiniMaxAI/MiniMax-M3', self.aliases.for_provider('novita'))
        self.assertNotIn('deepseek-v4-pro', self.aliases.for_provider('openrouter'))

    def test_native_credit_units_and_eur_never_become_usd(self):
        for provider, unit in [('databricks', 'DBU'), ('snowflake', 'AI_CREDIT'), ('scaleway', 'EUR'), ('ovhcloud', 'EUR')]:
            with self.subTest(provider=provider):
                row = self.quotes(provider)[0]
                o, p = normalize(row, self.aliases, TIME, HASH)
                self.assertEqual(o['quote_unit'], unit)
                self.assertEqual(p['currency'], 'EUR' if unit == 'EUR' else None)
                with self.assertRaises(ValueError):
                    normalize(dict(row, currency='USD'), self.aliases, TIME, HASH)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.csv'
            path.write_text('offering_id,observed_at,input_per_million,output_per_million,cache_read_per_million,cache_write_per_million,currency,source_url,source_sha256\na,2026-10-26T00:00:00Z,1,2,,,,https://example.com,' + HASH + '\n')
            self.assertIsNone(read_history(path)[0]['currency'])
        self.assertTrue(all(r['variant'] == 'preview' and 'Preview Terms' in r['pricing_notes'] for r in self.quotes('snowflake')))
        fast = next(r for r in self.quotes('cloudflare') if r['provider_model_id'] == '@cf/meta/llama-3.3-70b-instruct-fp8-fast')
        self.assertEqual((fast['quantization'], fast['variant']), ('fp8', 'fast'))

    def test_xai_and_minimax_keep_complete_prompt_and_tier_schedules(self):
        rows = self.quotes('xai')
        self.assertEqual([(r['min_input_tokens'], r['max_input_tokens']) for r in rows], [(0, 199999), (200000, None)])
        body = fixture('xai')
        body['documents'][0]['body'] = '\n'.join(line for line in body['documents'][0]['body'].splitlines() if 'grok-4.7 (≥' not in line)
        with self.assertRaises(ValueError): self.quotes('xai', body)
        rows = self.quotes('minimax')
        self.assertEqual([(r['service_tier'], r['min_input_tokens'], r['max_input_tokens'], r['input_per_million']) for r in rows],
                         [('standard', 0, 512000, .3), ('standard', 512001, None, .6), ('priority', 0, 512000, .45), ('priority', 512001, None, .9)])
        body = fixture('minimax')
        body['documents'][0]['body'] = body['documents'][0]['body'].replace('512k', '256k')
        with self.assertRaises(ValueError): self.quotes('minimax', body)

    def test_deepseek_requires_reviewed_served_version_and_schedule(self):
        rows = self.quotes('deepseek')
        self.assertEqual(len({r['region'] for r in rows}), 2)
        self.assertEqual([r['input_per_million'] for r in rows], [.3, .15, 1.32, .66])
        for old, new in [('DeepSeek-V4.1-Flash-1017', 'DeepSeek-V4.1-Flash-1026'), ('01:00 - 04:00', '02:00 - 04:00')]:
            body = fixture('deepseek')
            body['documents'][0]['body'] = body['documents'][0]['body'].replace(old, new)
            with self.assertRaises(ValueError): self.quotes('deepseek', body)
        self.assertTrue(INVENTORY_PROVIDERS['deepseek'].fetch_source.endswith('/pricing/'))
        self.assertFalse(INVENTORY_PROVIDERS['deepseek'].SOURCE.endswith('/'))

    def test_dynamic_extra_components_duplicates_missing_routes_and_units_fail_closed(self):
        cases = []
        p = fixture('openrouter'); p['catalog']['data'][0]['pricing']['prompt'] = '-1'; cases.append(('openrouter', p))
        p = fixture('openrouter'); p['catalog']['data'][0]['pricing']['request'] = '.01'; cases.append(('openrouter', p))
        p = fixture('openrouter'); p['catalog']['data'].append(p['catalog']['data'][0]); cases.append(('openrouter', p))
        p = fixture('huggingface'); p['catalog']['data'][0]['providers'] = []; cases.append(('huggingface', p))
        p = fixture('huggingface'); p['catalog']['data'][0]['architecture']['output_modalities'] = ['image']; cases.append(('huggingface', p))
        p = fixture('nebius'); p['catalog'][0]['flavors'][0]['external_provider'] = True; cases.append(('nebius', p))
        p = fixture('nebius'); p['catalog'][0]['status'] = 'retired'; cases.append(('nebius', p))
        p = fixture('oracle'); p['catalog']['items'][0]['metricName'] = '10,000 Transactions'; cases.append(('oracle', p))
        p = fixture('scaleway'); p['catalog']['products'][0]['price']['retail_price']['currency_code'] = 'USD'; cases.append(('scaleway', p))
        p = fixture('snowflake'); p['pdf_document']['pages'] = []; cases.append(('snowflake', p))
        p = fixture('snowflake');
        for page in p['pdf_document']['pages']: page['text'] = page['text'].replace('subject to the Preview Terms', 'subject to changed terms')
        cases.append(('snowflake', p))
        p = fixture('databricks'); p['documents'][0]['body'] = p['documents'][0]['body'].replace('DBU Per 1M Tokens', 'DBU Per Hour'); cases.append(('databricks', p))
        p = fixture('ovhcloud'); p['reviewed_price_cards']['body'] = p['reviewed_price_cards']['body'].replace('€', '$'); cases.append(('ovhcloud', p))
        p = fixture('alibaba'); p['documents'][0]['body'] = p['documents'][0]['body'].replace('flat-rate pricing', 'tiered pricing'); cases.append(('alibaba', p))
        p = fixture('cloudflare'); p['documents'][0]['body'] = p['documents'][0]['body'].replace('per M input tokens', 'per K input tokens'); cases.append(('cloudflare', p))
        p = fixture('zai'); p['documents'][0]['body'] = p['documents'][0]['body'].replace('Prices per 1M tokens.', 'Prices per 1K tokens.'); cases.append(('zai', p))
        for provider, payload in cases:
            with self.subTest(provider=provider), self.assertRaises((ValueError, KeyError)):
                self.quotes(provider, payload)

    def test_review_failure_retains_quotes_but_allows_valid_native_evidence(self):
        collector = INVENTORY_PROVIDERS['openrouter']
        body = fixture('openrouter')['catalog']
        body['total_count'] = len(body['data'])  # Complete bounded replay, not the full live endpoint.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('providers.expanded.fetch_text', return_value=json.dumps(body)):
                self.assertEqual(run(root, ['openrouter'], strict=True), 0)
            before = {name: (root / name).read_bytes() for name in ('offerings.json', 'latest_prices.json', 'price_history.csv')}
            body['data'][0]['pricing']['request'] = '.01'
            with patch('providers.expanded.fetch_text', return_value=json.dumps(body)):
                self.assertEqual(run(root, ['openrouter'], strict=True), 1)
            self.assertEqual(before, {name: (root / name).read_bytes() for name in before})
            self.assertTrue((root / 'provider_catalogs/openrouter.json').exists())

    def test_fixture_checksums_and_bounded_provenance(self):
        manifest = json.loads((FIXTURES / 'manifest.json').read_text())
        for provider in PROVIDERS:
            raw = (FIXTURES / (provider + '.json')).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest[provider]['fixture_sha256'])
            self.assertEqual(len(raw), manifest[provider]['bytes'])
            self.assertLess(len(raw), 150000)


if __name__ == '__main__': unittest.main()
