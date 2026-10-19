"""Operator pauses and DeepSeek source completeness; no production writes/calls."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers import together
from providers.deepseek_pricing import parse_models
from providers.expanded import INVENTORY_PROVIDERS
from scripts.collect import run
from scripts.catalog_inventory import normalize_inventory

ROOT = Path(__file__).resolve().parent.parent
BODY = (ROOT / 'tests/fixtures/deepseek-pricing.html').read_text()


class TogetherPauseTests(unittest.TestCase):
    def test_pause_uses_only_free_docs_even_when_a_key_exists(self):
        body = (ROOT / 'tests/fixtures/together.md').read_text()
        with patch.dict(os.environ, {'TOGETHER_API_KEY': 'test-only-secret'}), patch('providers.together.fetch_text', return_value=body) as fetch:
            result = together.collect({})
        fetch.assert_called_once_with(together.FETCH_URL)
        self.assertTrue(result.inventory_only)
        self.assertEqual(result.records, [])
        self.assertFalse(result.authoritative_catalog)
        self.assertIsNone(result.parse_error)
        self.assertIsNone(result.fallback_reason)  # Intentional policy, not a failed API.

    def test_inventory_check_preserves_quotes_history_and_availability(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            # Copy reviewed inputs only, into a disposable test directory.
            names = ['offerings.json', 'models.json', 'latest_prices.json', 'price_history.csv', 'price_history.json', 'changes.json', 'status.json']
            for name in names:
                (path / name).write_bytes((ROOT / 'data' / name).read_bytes())
            before = {n: (path / n).read_bytes() for n in names if n != 'status.json'}
            with patch('providers.together.fetch_text', return_value=(ROOT / 'tests/fixtures/together.md').read_text()):
                self.assertEqual(run(path, ['together'], strict=True), 0)
            for name, original in before.items():
                self.assertEqual((path / name).read_bytes(), original, name)
            status = next(p for p in json.loads((path / 'status.json').read_text())['providers'] if p['id'] == 'together')
            self.assertEqual((status['state'], status['collection_scope'], status['offering_count']), ('ok', 'inventory_only', 0))
            self.assertTrue((path / 'provider_catalogs/together.json').exists())


class DeepSeekCompletenessTests(unittest.TestCase):
    def test_exact_columns_versions_and_time_of_use_rates(self):
        models = parse_models(BODY)
        self.assertEqual([m['native_id'] for m in models], ['deepseek-flash', 'deepseek-v4-pro'])
        flash = models[0]
        self.assertEqual(flash['version'], 'DeepSeek-V4.1-Flash-1017')
        values = {(r['dimension'], r['conditions']['time_of_use']): r['amount'] for r in flash['rates']}
        self.assertEqual(values, {('cache_read', 'OFF-PEAK'): '0.003', ('cache_read', 'PEAK'): '0.006', ('input', 'OFF-PEAK'): '0.15', ('input', 'PEAK'): '0.3', ('output', 'OFF-PEAK'): '0.6', ('output', 'PEAK'): '1.2'})
        self.assertTrue(all('Chinese public holidays' in r['conditions']['peak_schedule'] for r in flash['rates']))
        self.assertEqual(flash['context'], '1M')  # Do not guess decimal/binary capacity.

    def test_partial_tool_only_ambiguous_units_and_missing_prices_fail_closed(self):
        cases = [BODY[BODY.index('<h2>Search'):], BODY.replace('units of per 1M tokens', 'units unknown'),
                 BODY.replace('<td>$0.3</td>', ''), BODY.replace('$0.3', 'Contact sales'),
                 BODY.replace('OFF-PEAK', 'UNKNOWN'), BODY.replace('Peak hours are', 'Unconfirmed hours are'),
                 BODY.replace('rowspan="6"', 'rowspan="99"'), BODY.replace('deepseek-v4-pro</td>', 'deepseek-flash</td>'),
                 BODY.replace('deepseek-v4-pro</td>', 'deepseek-other</td>'),
                 BODY.replace('units of per 1M tokens', 'units unknown') + '<script>units of per 1M tokens</script>']
        for body in cases:
            with self.subTest(body=body[:65]), self.assertRaises(ValueError):
                parse_models(body)

    def test_failed_partial_snapshot_retains_last_good_native_catalog_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with patch('providers.expanded.fetch_text', return_value=BODY):
                self.assertEqual(run(path, ['deepseek'], strict=True), 0)
            before = {name: (path / name).read_bytes() for name in ['provider_catalogs/deepseek.json', 'inventory_history.jsonl']}
            with patch('providers.expanded.fetch_text', return_value=BODY[BODY.index('<h2>Search'):]):
                self.assertEqual(run(path, ['deepseek'], strict=True), 1)
            self.assertEqual(before, {name: (path / name).read_bytes() for name in before})
            self.assertEqual(json.loads((path / 'status.json').read_text())['providers'][0]['state'], 'error')

    def test_collector_rejects_partial_page_and_structured_records_remain_native(self):
        with patch('providers.expanded.fetch_text', return_value='<table><tr><td>API</td><td>Price</td></tr><tr><td>Search</td><td>$0.75</td></tr></table>'):
            with self.assertRaisesRegex(ValueError, 'complete model pricing table'):
                INVENTORY_PROVIDERS['deepseek'].collect({})
        with patch('providers.expanded.fetch_text', return_value=BODY):
            result = INVENTORY_PROVIDERS['deepseek'].collect({})
        doc, _ = normalize_inventory('deepseek', result.source_payload, result.source_kind)
        models = [r for r in doc['records'] if r['kind'] == 'model']
        self.assertEqual(len(models), 2)
        self.assertTrue(any(r['kind'] == 'document_row' for r in doc['records']))
        self.assertTrue(all(r['comparison_eligible'] is False for r in doc['records']))
        self.assertEqual(result.records, [])
        self.assertTrue(all(len(r['rates']) == 6 for r in models))
        changed = BODY.replace('$0.3</td>', '$0.2</td>')
        with patch('providers.expanded.fetch_text', return_value=changed):
            newer = INVENTORY_PROVIDERS['deepseek'].collect({})
        after, _ = normalize_inventory('deepseek', newer.source_payload, newer.source_kind)
        self.assertEqual({r['id'] for r in models}, {r['id'] for r in after['records'] if r['kind'] == 'model'})


if __name__ == '__main__':
    unittest.main()
