"""Issue 43: explicit EUR source proposal and transient Nebius status evidence."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.comparison_expansion import ovhcloud_quotes
from providers.expanded import INVENTORY_PROVIDERS
from providers.reviewed_inventory import reviewed_quotes
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import run
from scripts.normalize import catalog

FIXTURES = Path(__file__).parent / 'fixtures'
CAPTURES = FIXTURES / 'issue-43'
OLD_SOURCE = 'https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/'
EUR_SOURCE = 'https://www.ovhcloud.com/en-ie/public-cloud/ai-endpoints/catalog/'


class Issue43Tests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()

    def ovh_quotes(self, body, source=EUR_SOURCE):
        return ovhcloud_quotes({'reviewed_price_cards': {'source_url': source, 'body': body}},
                               self.aliases.for_provider('ovhcloud'), source)

    def test_capture_provenance(self):
        manifest = json.loads((CAPTURES / 'manifest.json').read_text())
        for filename, info in manifest['sources'].items():
            raw = (CAPTURES / filename).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), info['excerpt_sha256'])
            self.assertEqual(len(raw), info['excerpt_bytes'])
            self.assertLess(len(raw), 128 * 1024)
            self.assertGreater(info['parent_bytes'], len(raw))

    def test_ireland_cards_preserve_all_quote_fields_except_actual_source_url(self):
        legacy = json.loads((FIXTURES / 'provider-comparisons/ovhcloud.json').read_text())
        expected = self.ovh_quotes(legacy['reviewed_price_cards']['body'], OLD_SOURCE)
        actual = self.ovh_quotes((CAPTURES / 'ovhcloud-en-ie.html').read_text())
        self.assertEqual(actual, [dict(row, source_url=EUR_SOURCE) for row in expected])
        self.assertEqual([(r['input_per_million'], r['output_per_million'], r['currency']) for r in actual],
                         [(0.08, 0.4, 'EUR'), (0.04, 0.15, 'EUR')])

    def test_failed_run_dollar_cards_remain_rejected(self):
        with self.assertRaisesRegex(ValueError, 'explicit EUR/token'):
            self.ovh_quotes((CAPTURES / 'ovhcloud-en.html').read_text(), OLD_SOURCE)

    def test_proposed_cards_reject_ambiguous_units_currency_and_completeness(self):
        body = (CAPTURES / 'ovhcloud-en-ie.html').read_text()
        for bad in [body.replace('€', '$'), body.replace('Mtoken', 'Ktoken'),
                    body.replace('(input)', '(output)'), body + body,
                    body.replace('€0.08', '€-0.08'), body.replace('€0.08', '€0.08€')]:
            with self.subTest(body=bad), self.assertRaises(ValueError):
                self.ovh_quotes(bad)
        for source in [EUR_SOURCE.replace('en-ie', 'en-gb'), EUR_SOURCE + '?currency=EUR']:
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'Unreviewed'):
                self.ovh_quotes(body, source)

    def test_collector_requests_exact_eur_page_and_preserves_native_currency_unknown(self):
        payload = json.loads((FIXTURES / 'provider-comparisons/ovhcloud.json').read_text())
        collector = INVENTORY_PROVIDERS['ovhcloud']
        responses = {collector.SOURCE: json.dumps(payload['catalog']),
                     EUR_SOURCE: (CAPTURES / 'ovhcloud-en-ie.html').read_text()}
        with patch('providers.expanded.fetch_text', side_effect=responses.__getitem__) as fetch:
            result = collector.collect(self.aliases)
        self.assertEqual([call.args[0] for call in fetch.call_args_list], [collector.SOURCE, EUR_SOURCE])
        self.assertIsNone(result.parse_error)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.source_urls, [collector.SOURCE, EUR_SOURCE])
        native, _ = normalize_inventory('ovhcloud', result.source_payload, result.source_kind)
        self.assertTrue(all(r['comparison_eligible'] is False for r in native['records']))
        self.assertTrue(all(r['billing'].get('currency') is None for r in native['records']))

    def test_nebius_error_fails_closed_and_recovered_capture_validates_all_bindings(self):
        collector = INVENTORY_PROVIDERS['nebius']
        failed = json.loads((CAPTURES / 'nebius-error.json').read_text())
        self.assertEqual([f['model_id'] for r in failed if r['status'] != 'active' for f in r['flavors']],
                         ['Qwen/Qwen3.8-27B'])
        with self.assertRaisesRegex(ValueError, 'Nebius model is not active'):
            reviewed_quotes('nebius', {'catalog': failed}, self.aliases, collector.SOURCE)
        recovered = json.loads((CAPTURES / 'nebius-active.json').read_text())
        rows = reviewed_quotes('nebius', {'catalog': recovered}, self.aliases, collector.SOURCE)
        self.assertEqual({r['provider_model_id'] for r in rows}, set(self.aliases.for_provider('nebius')))
        self.assertEqual(len(rows), 5)

    def test_nebius_error_retains_reviewed_prices_history_and_availability(self):
        collector = INVENTORY_PROVIDERS['nebius']
        active = (CAPTURES / 'nebius-active.json').read_text()
        failed = (CAPTURES / 'nebius-error.json').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('providers.expanded.fetch_text', return_value=active):
                self.assertEqual(run(root, ['nebius'], strict=True), 0)
            files = ('offerings.json', 'latest_prices.json', 'price_history.csv', 'changes.json')
            before = {f: (root / f).read_bytes() for f in files}
            with patch('providers.expanded.fetch_text', return_value=failed):
                self.assertEqual(run(root, ['nebius'], strict=True), 1)
            self.assertEqual(before, {f: (root / f).read_bytes() for f in files})
            self.assertEqual(json.loads((root / 'status.json').read_text())['providers'][0]['state'], 'error')


if __name__ == '__main__':
    unittest.main()
