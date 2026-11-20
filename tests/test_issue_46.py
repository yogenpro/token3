"""Replay bounded public pricing excerpts from the failed collection attempt."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.expanded import INVENTORY_PROVIDERS
from providers.policy import excluded_model_ids
from providers.reviewed_inventory import reviewed_quotes
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import read_history, run
from scripts.normalize import catalog

FIXTURES = Path(__file__).parent / 'fixtures/issue-46'
QUOTE_FIELDS = ('provider_model_id', 'variant', 'min_input_tokens', 'max_input_tokens',
                'input_per_million', 'output_per_million', 'cache_read_per_million')
VERCEL_EXCLUSIONS = {'nvidia/nemotron-3-nano-30b-a3b', 'inception/mercury-2',
                     'inception/mercury-2.5', 'minimax/minimax-m2'}
IRELAND_CARDS = 'https://www.ovhcloud.com/en-ie/public-cloud/ai-endpoints/catalog/'
LEGACY_CARDS = 'https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/'


class Issue46PricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.aliases = catalog()
        cls.baseline = json.loads((FIXTURES / 'last-good-quotes.json').read_text())
        cls.alibaba = (FIXTURES / 'alibaba-singapore.md').read_text()

    def alibaba_quotes(self, body):
        source = INVENTORY_PROVIDERS['alibaba'].SOURCE
        return reviewed_quotes('alibaba', {'documents': [{'source_url': source, 'body': body}]},
                               self.aliases, source)

    def snowflake_quotes(self, pdf):
        source = INVENTORY_PROVIDERS['snowflake'].SOURCE
        return reviewed_quotes('snowflake', {'pdf_document': pdf}, self.aliases, source)

    def assert_quotes(self, provider, rows, unit, currency, region, source):
        values = [[row[field] for field in QUOTE_FIELDS] for row in rows]
        self.assertEqual(sorted(values), sorted(self.baseline[provider]))
        self.assertEqual({(r.get('quote_unit', 'USD'), r['currency'], r['region'], r['source_url'],
                           r['service_tier'], r['cache_write_per_million']) for r in rows},
                         {(unit, currency, region, source, 'standard', None)})

    def test_fixture_excerpts_match_the_manifest(self):
        manifest = json.loads((FIXTURES / 'manifest.json').read_text())
        for filename, evidence in manifest['fixtures'].items():
            excerpt = (FIXTURES / filename).read_bytes()
            with self.subTest(filename=filename):
                self.assertEqual(len(excerpt), evidence['bytes'])
                self.assertEqual(hashlib.sha256(excerpt).hexdigest(), evidence['sha256'])
        pdf = json.loads((FIXTURES / 'snowflake-table.json').read_text())
        self.assertEqual(pdf['response_sha256'], manifest['sources']['snowflake']['failed_document_sha256'])

    def test_alibaba_rewording_preserves_all_seventeen_quotes(self):
        self.assert_quotes('alibaba', self.alibaba_quotes(self.alibaba), 'USD', 'USD',
                           'Singapore / International', INVENTORY_PROVIDERS['alibaba'].SOURCE)

    def test_alibaba_changed_billing_semantics_still_fail_closed(self):
        for before, after in [
            ('K indicates 1,000', 'K indicates 1,024'),
            ('20% off for a limited time', '25% off for a limited time'),
            ('Current capabilities are equivalent to qwen3.7-plus-2026-05-26',
             'Current capabilities are equivalent to qwen3.7-plus-2026-06-26'),
            ('Input unit price (per million tokens)', 'Input unit price (per thousand tokens)'),
            ('No tier distinction', 'Tier-specific rates'),
            ('Non-thinking and thinking modes', 'Thinking mode only'),
            ('1 million Tokens</td><td></td>', '1 million Tokens</td><td>Required surcharge</td>'),
            ('32K&lt;Token≤256K', '32K&lt;Token≤128K'),
        ]:
            self.assertIn(before, self.alibaba)
            with self.subTest(after=after), self.assertRaises(ValueError):
                self.alibaba_quotes(self.alibaba.replace(before, after, 1))

    def test_snowflake_shared_caption_preserves_cortex_inference_prices(self):
        pdf = json.loads((FIXTURES / 'snowflake-table.json').read_text())
        rows = self.snowflake_quotes(pdf)
        self.assert_quotes('snowflake', rows, 'AI_CREDIT', None, 'native AI Credit schedule',
                           INVENTORY_PROVIDERS['snowflake'].pdf_url)
        for row in rows:
            self.assertIn('Preview Terms', row['pricing_notes'])
        cache_write_amounts = {'claude-opus-5-5': '2.5', 'glm-5.3': '1.05', 'kimi-k3': '1.875'}
        for row in rows:
            self.assertIn('Cache-write amount ' + cache_write_amounts[row['provider_model_id']],
                          row['pricing_notes'])

    def test_snowflake_rejects_other_products_and_unaligned_continuation(self):
        for before, after in [
            ('Cortex Inference with Prompt Caching, Cortex Sense', 'Cortex Sense'),
            ('AI Credits per one million Tokens', 'Platform Credits per one million Tokens'),
            ('Cache Write', 'Cache Read'),
        ]:
            pdf = json.loads((FIXTURES / 'snowflake-table.json').read_text())
            page = pdf['pages'][2]
            self.assertIn(before, page['text'])
            page['text'] = page['text'].replace(before, after, 1)
            with self.subTest(after=after), self.assertRaises(ValueError):
                self.snowflake_quotes(pdf)

    def test_ovhcloud_uses_ireland_eur_cards_and_preserves_reviewed_scope(self):
        collector = INVENTORY_PROVIDERS['ovhcloud']
        baseline = json.loads((FIXTURES.parent / 'provider-comparisons/ovhcloud.json').read_text())
        expected = reviewed_quotes('ovhcloud', baseline, self.aliases, collector.SOURCE)
        responses = {collector.SOURCE: json.dumps(baseline['catalog']),
                     IRELAND_CARDS: (FIXTURES / 'ovhcloud-en-ie.html').read_text()}
        with patch('providers.expanded.fetch_text', side_effect=responses.__getitem__) as fetch:
            result = collector.collect(self.aliases)
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [collector.SOURCE, IRELAND_CARDS])
        self.assertEqual(result.source_urls, [collector.SOURCE, IRELAND_CARDS])
        self.assertIsNone(result.parse_error)
        self.assertEqual(result.records, [dict(row, source_url=IRELAND_CARDS) for row in expected])
        native, _ = normalize_inventory('ovhcloud', result.source_payload, result.source_kind)
        self.assertTrue(native['records'])
        self.assertTrue(all(r['comparison_eligible'] is False and r['billing'].get('currency') is None
                            for r in native['records']))

    def test_ovhcloud_rejects_dollars_ambiguous_cards_and_other_source_urls(self):
        collector = INVENTORY_PROVIDERS['ovhcloud']
        eur = (FIXTURES / 'ovhcloud-en-ie.html').read_text()
        dollars = (FIXTURES / 'ovhcloud-en.html').read_text()
        for body, url in [(dollars, LEGACY_CARDS), (dollars, IRELAND_CARDS),
                          (eur + eur, IRELAND_CARDS), (eur.replace('Mtoken', 'Ktoken'), IRELAND_CARDS),
                          (eur, IRELAND_CARDS.replace('en-ie', 'en-gb'))]:
            payload = {'reviewed_price_cards': {'source_url': url, 'body': body}}
            with self.subTest(url=url, body_size=len(body)), self.assertRaises(ValueError):
                reviewed_quotes('ovhcloud', payload, self.aliases, collector.SOURCE)

    def test_vercel_exclusions_are_exact_and_reappearing_rows_remain_native(self):
        self.assertEqual(excluded_model_ids('vercel'), VERCEL_EXCLUSIONS)
        collector = INVENTORY_PROVIDERS['vercel']
        legacy = json.loads((FIXTURES.parent / 'issue-38/vercel-reviewed.json').read_text())['catalog']['data']
        original = json.loads((FIXTURES.parent / 'vercel-reviewed-expansion.json').read_text())['data']
        listing = [row for row in legacy if row['id'] not in VERCEL_EXCLUSIONS]
        restored = [row for row in legacy + original if row['id'] in VERCEL_EXCLUSIONS]
        self.assertEqual({row['id'] for row in restored}, VERCEL_EXCLUSIONS)
        self.assertEqual(len(restored), len(VERCEL_EXCLUSIONS))
        with patch('providers.expanded.fetch_text', return_value=json.dumps({'data': listing + restored})):
            result = collector.collect(self.aliases)
        self.assertIsNone(result.parse_error)
        self.assertFalse(result.authoritative_catalog)
        native, _ = normalize_inventory('vercel', result.source_payload, result.source_kind)
        self.assertTrue(VERCEL_EXCLUSIONS.issubset({row['native_id'] for row in native['records']}))
        self.assertTrue(all(row['comparison_eligible'] is False for row in native['records']))
        expected = reviewed_quotes('vercel', {'catalog': {'data': listing}}, self.aliases, collector.SOURCE)
        self.assertEqual(expected, result.records)
        self.assertEqual({r['provider_model_id'] for r in expected},
                         set(self.aliases.for_provider('vercel')) - VERCEL_EXCLUSIONS)
        for mid in ('inception/mercury-3', 'minimax/minimax-m2.1', 'minimax/minimax-m2.5'):
            without = {'catalog': {'data': [row for row in listing if row['id'] != mid]}}
            with self.subTest(mid=mid), self.assertRaisesRegex(ValueError, 'Tracked model.*missing.*' + mid):
                reviewed_quotes('vercel', without, self.aliases, collector.SOURCE)

    def test_vercel_preserves_last_good_prices_and_availability_for_excluded_ids(self):
        source_data = FIXTURES.parent.parent.parent / 'data'
        legacy = json.loads((FIXTURES.parent / 'issue-38/vercel-reviewed.json').read_text())['catalog']['data']
        listing = [row for row in legacy if row['id'] not in VERCEL_EXCLUSIONS]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('offerings.json', 'latest_prices.json', 'price_history.csv', 'changes.json'):
                (root / name).write_bytes((source_data / name).read_bytes())
            before = json.loads((root / 'offerings.json').read_text())
            retained = [row for row in before if row['provider'] == 'vercel'
                        and row['provider_model_id'] in VERCEL_EXCLUSIONS]
            self.assertEqual({row['provider_model_id'] for row in retained}, VERCEL_EXCLUSIONS)
            ids = {row['id'] for row in retained}
            old_prices = json.loads((root / 'latest_prices.json').read_text())
            old_history = read_history(root / 'price_history.csv')
            with patch('providers.expanded.fetch_text', return_value=json.dumps({'data': listing})):
                self.assertEqual(run(root, ['vercel'], strict=True), 0)
            self.assertEqual([row for row in json.loads((root / 'offerings.json').read_text()) if row['id'] in ids], retained)
            prices = json.loads((root / 'latest_prices.json').read_text())
            self.assertEqual([row for row in prices if row['offering_id'] in ids],
                             [row for row in old_prices if row['offering_id'] in ids])
            self.assertEqual(read_history(root / 'price_history.csv')[:len(old_history)], old_history)
