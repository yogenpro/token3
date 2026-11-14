"""Issue 38: an exact operator exclusion, without inferred Vercel retirement."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.expanded import INVENTORY_PROVIDERS
from providers.policy import excluded_model_ids
from providers.reviewed_inventory import vercel_quotes
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import read_history, run
from scripts.normalize import ROOT, catalog

CAPTURES = ROOT / 'tests/fixtures/issue-38'
EXCLUDED = 'nvidia/nemotron-3-nano-30b-a3b'
SOURCE = INVENTORY_PROVIDERS['vercel'].SOURCE


class Issue38Tests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()
        self.bindings = self.aliases.for_provider('vercel')
        self.payload = json.loads((CAPTURES / 'vercel-reviewed.json').read_text())

    def test_public_capture_provenance_and_conflicting_model_page(self):
        manifest = json.loads((CAPTURES / 'manifest.json').read_text())
        for filename, source in manifest['sources'].items():
            raw = (CAPTURES / filename).read_bytes()
            self.assertEqual(len(raw), source['excerpt_bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source['excerpt_sha256'])
            self.assertLess(len(raw), 128 * 1024)
            self.assertRegex(source['parent_sha256'], r'^[a-f0-9]{64}$')
        self.assertIn(EXCLUDED, (CAPTURES / 'vercel-model.md').read_text())
        actual = {r['id'] for r in self.payload['catalog']['data']}
        self.assertEqual(set(self.bindings) - actual, {EXCLUDED})

    def test_without_policy_the_reported_missing_binding_still_fails(self):
        with patch.dict('providers.policy.POLICIES', {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'Tracked model.*missing.*' + EXCLUDED):
                vercel_quotes(self.payload, self.bindings, SOURCE)

    def test_exact_exclusion_preserves_every_other_reviewed_quote_field(self):
        self.assertEqual(excluded_model_ids('vercel'), {EXCLUDED})
        remaining = {k: v for k, v in self.bindings.items() if k != EXCLUDED}
        with patch.dict('providers.policy.POLICIES', {}, clear=True):
            expected = vercel_quotes(self.payload, remaining, SOURCE)
        actual = vercel_quotes(self.payload, self.bindings, SOURCE)
        self.assertEqual(actual, expected)
        self.assertEqual({r['provider_model_id'] for r in actual}, set(remaining))

    def test_excluded_quote_does_not_resume_on_reappearance_but_native_evidence_survives(self):
        original = json.loads((ROOT / 'tests/fixtures/vercel-reviewed-expansion.json').read_text())
        restored = next(r for r in original['data'] if r['id'] == EXCLUDED)
        self.payload['catalog']['data'].append(restored)
        with patch('providers.expanded.fetch_text', return_value=json.dumps(self.payload['catalog'])):
            result = INVENTORY_PROVIDERS['vercel'].collect(self.bindings)
        self.assertIsNone(result.parse_error)
        self.assertNotIn(EXCLUDED, {r['provider_model_id'] for r in result.records})
        native, _ = normalize_inventory('vercel', result.source_payload, 'api')
        self.assertIn(EXCLUDED, {r['native_id'] for r in native['records']})
        self.assertTrue(all(r['comparison_eligible'] is False for r in native['records']))

    def test_other_missing_bindings_currency_and_rate_errors_still_fail(self):
        for change in ('missing', 'currency', 'rate', 'duplicate'):
            payload = copy.deepcopy(self.payload)
            rows = payload['catalog']['data']
            if change == 'missing':
                rows.pop(0)
            elif change == 'currency':
                rows[0]['pricing']['currency'] = 'EUR'
            elif change == 'rate':
                rows[0]['pricing'].pop('input')
            else:
                duplicate = copy.deepcopy(rows[0])
                duplicate['pricing']['input'] = '1'
                rows.append(duplicate)
            with self.subTest(change=change), self.assertRaises(ValueError):
                vercel_quotes(payload, self.bindings, SOURCE)

    def test_collection_retains_excluded_prices_flags_history_and_strict_failure_reporting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ('models.json', 'offerings.json', 'latest_prices.json', 'price_history.csv', 'price_history.json', 'changes.json', 'status.json')
            for name in names:
                (root / name).write_bytes((ROOT / 'data' / name).read_bytes())
            before = {name: json.loads((root / name).read_text()) for name in names if name.endswith('.json')}
            retained = {r['id'] for r in before['offerings.json'] if r['provider'] == 'vercel' and r['provider_model_id'] == EXCLUDED}
            self.assertTrue(retained)
            original_history = read_history(root / 'price_history.csv')
            with patch('providers.expanded.fetch_text', return_value=json.dumps(self.payload['catalog'])):
                self.assertEqual(run(root, ['vercel'], strict=True), 0)
            for name, key in [('offerings.json', 'id'), ('latest_prices.json', 'offering_id')]:
                self.assertEqual([r for r in before[name] if r[key] in retained],
                                 [r for r in json.loads((root / name).read_text()) if r[key] in retained])
            self.assertEqual(read_history(root / 'price_history.csv')[:len(original_history)], original_history)
            after_changes = json.loads((root / 'changes.json').read_text())
            self.assertEqual([r for r in before['changes.json'] if r['offering_id'] in retained],
                             [r for r in after_changes if r['offering_id'] in retained])
            last_good = {name: (root / name).read_bytes() for name in ('offerings.json', 'latest_prices.json', 'price_history.csv')}
            incomplete = copy.deepcopy(self.payload['catalog'])
            incomplete['data'].pop(0)
            with patch('providers.expanded.fetch_text', return_value=json.dumps(incomplete)):
                self.assertEqual(run(root, ['vercel'], strict=True), 1)
            for name, raw in last_good.items():
                self.assertEqual((root / name).read_bytes(), raw)
            state = next(p for p in json.loads((root / 'status.json').read_text())['providers'] if p['id'] == 'vercel')
            self.assertEqual(state['state'], 'error')


if __name__ == '__main__':
    unittest.main()
