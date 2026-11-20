"""The xAI operator exclusion preserves the other reviewed prompt schedules."""
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.expanded import INVENTORY_PROVIDERS
from providers.policy import POLICIES, excluded_model_ids
from providers.reviewed_inventory import reviewed_quotes
from scripts.catalog_inventory import normalize_inventory
from scripts.normalize import catalog

FIXTURES = Path(__file__).parent / 'fixtures'
EXCLUDED = 'grok-build-0.1'


class Issue48Tests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()
        self.collector = INVENTORY_PROVIDERS['xai']
        self.current = (FIXTURES / 'issue-48/xai.md').read_text()
        self.prior = (FIXTURES / 'provider-coverage-review/xai.md').read_text()

    def quotes(self, body):
        source = self.collector.SOURCE
        return reviewed_quotes('xai', {'documents': [{'body': body, 'source_url': source}]},
                               self.aliases, source)

    def test_current_capture_keeps_every_other_reviewed_quote_unchanged(self):
        excerpt = self.current.encode()
        manifest = json.loads((FIXTURES / 'issue-48/manifest.json').read_text())
        self.assertEqual(manifest['official_source'], self.collector.SOURCE)
        self.assertEqual(len(excerpt), manifest['excerpt_bytes'])
        self.assertEqual(hashlib.sha256(excerpt).hexdigest(), manifest['excerpt_sha256'])
        with patch.dict(POLICIES, {'xai': {}}, clear=False):
            with self.assertRaisesRegex(ValueError, 'Incomplete xAI prompt schedule'):
                self.quotes(self.current)
            previous = self.quotes(self.prior)
        actual = self.quotes(self.current)
        self.assertEqual(len(actual), 8)
        order = lambda row: (row['provider_model_id'], row['min_input_tokens'])
        expected = [row for row in previous if row['provider_model_id'] != EXCLUDED]
        self.assertEqual(sorted(actual, key=order), sorted(expected, key=order))

    def test_exact_exclusion_does_not_resume_on_reappearance(self):
        self.assertEqual(excluded_model_ids('xai'), {EXCLUDED})
        self.assertIn(EXCLUDED, self.aliases.for_provider('xai'))
        with patch('providers.expanded.fetch_text', return_value=self.prior):
            result = self.collector.collect(self.aliases)
        self.assertIsNone(result.parse_error)
        self.assertFalse(result.authoritative_catalog)
        self.assertNotIn(EXCLUDED, {row['provider_model_id'] for row in result.records})
        native, _ = normalize_inventory('xai', result.source_payload, result.source_kind)
        labels = {row['label'] for row in native['records'] if row['label'].startswith(EXCLUDED + ' (')}
        self.assertEqual(labels, {EXCLUDED + ' (< 200k prompt tokens)', EXCLUDED + ' (≥ 200k prompt tokens)'})
        self.assertTrue(all(row['comparison_eligible'] is False for row in native['records']))

    def test_missing_other_binding_or_band_still_fails(self):
        for changed in ('grok-4.7 (< 200k prompt tokens)', 'grok-4.3 (≥ 200k prompt tokens)'):
            partial = '\n'.join(line for line in self.current.splitlines() if changed not in line)
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'Incomplete xAI prompt schedule'):
                self.quotes(partial)
