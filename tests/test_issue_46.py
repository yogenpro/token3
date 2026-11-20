"""Replay bounded public pricing excerpts from the failed collection attempt."""
import hashlib
import json
import unittest
from pathlib import Path

from providers.expanded import INVENTORY_PROVIDERS
from providers.reviewed_inventory import reviewed_quotes
from scripts.normalize import catalog

FIXTURES = Path(__file__).parent / 'fixtures/issue-46'
QUOTE_FIELDS = ('provider_model_id', 'variant', 'min_input_tokens', 'max_input_tokens',
                'input_per_million', 'output_per_million', 'cache_read_per_million')


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
