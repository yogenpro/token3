"""Bounded public-source regressions for collection run 45451893963."""
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from providers import mistral
from providers.coverage_expansion import PUBLIC_SOURCES
from providers.coverage_quotes import reviewed_quotes as coverage_quotes
from providers.expanded import INVENTORY_PROVIDERS
from providers.policy import POLICIES, excluded_model_ids
from providers.reviewed_inventory import reviewed_quotes
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import apply_snapshot
from scripts.normalize import catalog, normalize
from test_coverage_expansion import payload

FIXTURES = Path(__file__).parent / 'fixtures'
CAPTURES = FIXTURES / 'issue-59'


class Issue59PricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.aliases = catalog()

    def quotes(self, provider, body):
        source = INVENTORY_PROVIDERS[provider].SOURCE
        return reviewed_quotes(provider, {'documents': [{'source_url': source, 'body': body}]},
                               self.aliases, source)

    def test_public_excerpts_match_manifest(self):
        for name, evidence in json.loads((CAPTURES / 'manifest.json').read_text()).items():
            excerpt = (CAPTURES / name).read_bytes()
            with self.subTest(fixture=name):
                self.assertEqual(len(excerpt), evidence['bytes'])
                self.assertEqual(hashlib.sha256(excerpt).hexdigest(), evidence['sha256'])

    def test_alibaba_english_links_preserve_all_reviewed_quotes(self):
        original = (FIXTURES / 'issue-46/alibaba-singapore.md').read_text()
        current = (CAPTURES / 'alibaba-singapore.md').read_text()
        expected = self.quotes('alibaba', original)
        self.assertEqual(len(expected), 17)
        self.assertCountEqual(self.quotes('alibaba', current), expected)
        for old, new in [
            ('/en/model-studio/context-cache', '/en/model-studio/unreviewed-billing'),
            ('/en/model-studio/batch-interfaces-compatible-with-openai', '/en/model-studio/unreviewed-tier'),
            ('qwen3.7-max-2026-05-20', 'qwen3.7-max-2026-06-20'),
        ]:
            self.assertIn(old, current)
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.quotes('alibaba', current.replace(old, new))

    def test_mistral_current_html_preserves_the_six_standard_quotes(self):
        current = (CAPTURES / 'mistral.html').read_text()
        legacy = (FIXTURES / 'provider-coverage-review/mistral.md').read_text()
        expected = mistral.parse(legacy, self.aliases).records
        with patch.object(mistral, 'fetch_text', return_value=current) as fetch:
            result = mistral.collect(self.aliases)
        self.assertEqual(len(expected), 6)
        fetch.assert_called_once_with(mistral.SOURCE, headers={'Accept': 'text/html'})
        self.assertEqual(result.source_urls, [mistral.SOURCE])
        self.assertEqual(result.source_sha256, hashlib.sha256(current.encode()).hexdigest())
        self.assertIsNone(result.parse_error)
        self.assertCountEqual(result.records, expected)
        native, _ = normalize_inventory('mistral', result.source_payload, 'documentation')
        self.assertTrue(native['records'])
        self.assertTrue(all(not row['comparison_eligible'] for row in native['records']))

    def test_mistral_rejects_ambiguous_or_changed_html_scope(self):
        current = (CAPTURES / 'mistral.html').read_text()
        for old, new in [
            ('>Standard</span>', '>Batch</span>'),
            ('>USD<!-- -->', '>EUR<!-- -->'),
            ('/M Tokens', '/K Tokens'),
            ('codestral-2508', 'codestral-latest'),
            ('0.9', '0.09'),
            ('>Cached input</p>', '>Cache write</p>'),
        ]:
            self.assertIn(old, current)
            with self.subTest(changed=old):
                with patch.object(mistral, 'fetch_text', return_value=current.replace(old, new, 1)):
                    result = mistral.collect(self.aliases)
                self.assertTrue(result.parse_error)
                self.assertEqual(result.records, [])

    def test_xai_only_excludes_the_approved_build_id(self):
        prior = (FIXTURES / 'provider-coverage-review/xai.md').read_text()
        current = (CAPTURES / 'xai.md').read_text()
        excluded = 'grok-build-0.1'
        with patch.dict(POLICIES, {'xai': {}}):
            expected = [row for row in self.quotes('xai', prior) if row['provider_model_id'] != excluded]
        self.assertEqual(len(expected), 8)
        self.assertEqual(excluded_model_ids('xai'), {excluded})
        self.assertIn(excluded, self.aliases.for_provider('xai'))
        self.assertCountEqual(self.quotes('xai', current), expected)
        self.assertCountEqual(self.quotes('xai', prior), expected)
        with patch('providers.expanded.fetch_text', return_value=prior):
            result = INVENTORY_PROVIDERS['xai'].collect(self.aliases)
        self.assertIsNone(result.parse_error)
        self.assertFalse(result.authoritative_catalog)
        native, _ = normalize_inventory('xai', result.source_payload, result.source_kind)
        build = [row for row in native['records'] if row['label'].startswith(excluded + ' (')]
        self.assertEqual(len(build), 2)
        self.assertTrue(all(not row['comparison_eligible'] for row in build))
        missing = '\n'.join(line for line in current.splitlines() if 'grok-4.7 (< 200k' not in line)
        with self.assertRaisesRegex(ValueError, 'Incomplete xAI prompt schedule'):
            self.quotes('xai', missing)

    def test_upstage_collects_existing_list_rates_with_scope_unverified(self):
        original = payload('upstage')
        old = coverage_quotes('upstage', original, self.aliases)
        urls = json.loads((CAPTURES / 'manifest.json').read_text())
        responses = {doc['source_url']: doc['body'] for doc in original['documents']}
        for filename in ('upstage-pro.md', 'upstage-mini.md', 'upstage-chat.md'):
            responses[urls[filename]['url']] = (CAPTURES / filename).read_text()
        with patch('providers.coverage_expansion.fetch_text', side_effect=responses.__getitem__):
            result = PUBLIC_SOURCES['upstage'].collect(self.aliases)
        self.assertIsNone(result.parse_error)
        self.assertFalse(result.authoritative_catalog)
        self.assertEqual(set(result.source_urls), set(responses))
        fields = ('provider_model_id', 'input_per_million', 'output_per_million', 'cache_read_per_million',
                  'region', 'service_tier', 'currency', 'source_url')
        self.assertEqual([[r[k] for k in fields] for r in result.records],
                         [[r[k] for k in fields] for r in old])
        self.assertTrue(all(r['pricing_scope_unverified'] for r in result.records))
        previous = [normalize(row, self.aliases, '2026-11-22T00:00:00Z', '0' * 64) for row in old]
        offerings = {o['id']: dict(o, first_observed_at='2026-11-22T00:00:00Z') for o, _ in previous}
        latest = {offer['id']: price for offer, price in previous}
        history = [price.copy() for price in latest.values()]
        expected_history = list(history)
        identities = set(offerings)
        apply_snapshot('upstage', result, self.aliases, '2026-11-24T00:00:00Z', offerings, latest, history, [])
        self.assertEqual(set(offerings), identities)
        self.assertEqual(history, expected_history)
        self.assertTrue(all(o['pricing_scope_unverified'] for o in offerings.values()))
        native, _ = normalize_inventory('upstage', result.source_payload, result.source_kind)
        self.assertTrue(all(not row['comparison_eligible'] for row in native['records']))
        evidence = [r['billing'].get('text', '') for r in native['records']]
        self.assertTrue(any('$0.15/1M tokens' in t and 'promotional discount' in t for t in evidence))
        self.assertTrue(any('$0.05/1M tokens' in t and 'promotional discount' in t for t in evidence))

    def test_upstage_keeps_scope_quarantined_and_requires_exact_evidence(self):
        data = payload('upstage')
        urls = json.loads((CAPTURES / 'manifest.json').read_text())
        filenames = ('upstage-pro.md', 'upstage-mini.md', 'upstage-chat.md')
        documents = {urls[name]['url']: (CAPTURES / name).read_text() for name in filenames}
        for doc in data['documents']:
            doc['body'] = documents.get(doc['source_url'], doc['body'])
        witness = urls['upstage-chat.md']['url']
        data['documents'].append({'source_url': witness, 'body': documents[witness]})
        for old, new in [
            ('They continue to work', 'They have been retired'),
            ('### solar-pro-4-260806 (Alias: solar-pro-4)', '### solar-pro-4-261124 (Alias: solar-pro-4)'),
            ('## List price', '## Planning price'),
            ('cached per 1M tokens.', 'cached per 1K tokens.'),
        ]:
            broken = {'documents': [dict(doc, body=doc['body'].replace(old, new)) for doc in data['documents']]}
            self.assertNotEqual(broken['documents'], data['documents'])
            with self.subTest(changed=old), self.assertRaises(ValueError):
                coverage_quotes('upstage', broken, self.aliases)
        # Reverting to the old documented layout does not resume estimates.
        self.assertTrue(all(r['pricing_scope_unverified']
                            for r in coverage_quotes('upstage', payload('upstage'), self.aliases)))
