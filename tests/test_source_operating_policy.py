"""Bounded operator exclusions never invent retirement or successful checks."""
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.coverage_expansion import PUBLIC_SOURCES
from providers.coverage_quotes import reviewed_quotes
from providers.policy import POLICIES, collection_disabled, comparisons_paused, excluded_model_ids, validate_policy
from scripts.collect import PROVIDERS, read_history, run
from scripts.normalize import ROOT, catalog

BODY = (ROOT / 'tests/fixtures/issue-35/arcee.md').read_text()
EXCLUDED = {'deepseek/deepseek-v4-pro-0813', 'zai-org/glm-5.2'}


class SourceOperatingPolicyTests(unittest.TestCase):
    def test_bounded_live_source_fixtures_have_separate_capture_and_excerpt_provenance(self):
        root = ROOT / 'tests/fixtures/source-operating-policy'
        manifest = json.loads((root / 'manifest.json').read_text())
        for filename, source in manifest['sources'].items():
            raw = (root / filename).read_bytes()
            self.assertEqual(len(raw), source['excerpt_bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source['excerpt_sha256'])
            self.assertLess(len(raw), 128 * 1024)
            self.assertRegex(source['parent_sha256'], r'^[a-f0-9]{64}$')

    def test_enabled_scope_is_explicit_and_documented_without_removing_retained_sources(self):
        self.assertEqual(len(PROVIDERS), 47)
        enabled = [name for name in PROVIDERS if not collection_disabled(name)]
        self.assertEqual(len(enabled), 46)
        self.assertIn(f'{len(enabled)} enabled collectors', (ROOT / 'README.md').read_text())
        _, aliases = catalog()
        self.assertLessEqual(EXCLUDED, aliases.for_provider('arcee').keys())

    def test_exact_policy_scope_and_invalid_policies_fail_closed(self):
        self.assertEqual(excluded_model_ids('arcee'), EXCLUDED)
        self.assertFalse(comparisons_paused('arcee'))
        self.assertTrue(collection_disabled('castform'))
        self.assertTrue(comparisons_paused('castform'))
        self.assertFalse(collection_disabled('together'))
        for bad in [None, {}, {'reason': 'x', 'excluded_model_ids': []},
                    {'reason': 'x', 'excluded_model_ids': ['x', 'x']},
                    {'reason': 'x', 'excluded_model_ids': [' x']},
                    {'reason': 'x', 'excluded_model_ids': [False]},
                    dict(POLICIES['castform'], collection='healthy'),
                    dict(POLICIES['arcee'], authoritative_catalog=True)]:
            with self.subTest(policy=bad), self.assertRaises(ValueError):
                validate_policy(bad)

    def test_arcee_other_missing_rows_bad_units_and_duplicates_still_fail(self):
        _, aliases = catalog()
        duplicate = re.search(r'<tr><td>zai-org/glm-5.3-flash</td>.*?</tr>', BODY)[0]
        for body in [BODY.replace('moonshotai/kimi-k3', 'moonshotai/kimi-k3-unknown'),
                     BODY.replace('Prices per 1M Tokens.', 'Prices per 1K Tokens.'),
                     BODY.replace('</tbody>', duplicate + '</tbody>')]:
            payload = {'documents': [{'source_url': PUBLIC_SOURCES['arcee'].SOURCE, 'body': body}]}
            with self.subTest(body=body), self.assertRaises(ValueError):
                reviewed_quotes('arcee', payload, aliases)

    def test_arcee_excluded_rows_do_not_resume_if_they_reappear(self):
        _, aliases = catalog()
        rows = ''.join('<tr><td>' + mid + '</td><td>$1.00</td><td>$2.00</td><td>$0.10</td></tr>' for mid in EXCLUDED)
        payload = {'documents': [{'source_url': PUBLIC_SOURCES['arcee'].SOURCE, 'body': BODY.replace('</tbody>', rows + '</tbody>')}]}
        self.assertEqual(len(reviewed_quotes('arcee', payload, aliases)), 3)

    def test_disabled_collector_never_fetches_even_when_called_directly(self):
        with patch('providers.coverage_expansion.fetch_text') as fetch:
            with self.assertRaisesRegex(ValueError, 'Collection disabled by operator policy'):
                PUBLIC_SOURCES['castform'].collect({})
        fetch.assert_not_called()

    def test_explicit_disabled_selection_writes_nothing_and_preserves_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'not-created'
            with patch('providers.coverage_expansion.fetch_text') as fetch:
                self.assertEqual(run(root, ['castform'], strict=True), 0)
            fetch.assert_not_called()
            self.assertFalse(root.exists())

    def test_default_collection_skips_castform_and_retains_excluded_quotes_and_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('models.json', 'offerings.json', 'latest_prices.json', 'price_history.csv', 'price_history.json', 'changes.json', 'status.json'):
                (root / name).write_bytes((ROOT / 'data' / name).read_bytes())
            before_status = json.loads((root / 'status.json').read_text())
            before_offers = json.loads((root / 'offerings.json').read_text())
            before_prices = json.loads((root / 'latest_prices.json').read_text())
            before_history = read_history(root / 'price_history.csv')
            retained = {o['id'] for o in before_offers if o['provider'] == 'castform' or o['provider'] == 'arcee' and o['provider_model_id'] in EXCLUDED}
            with patch.dict('scripts.collect.PROVIDERS', {p: PUBLIC_SOURCES[p] for p in ('arcee', 'castform')}, clear=True), \
                    patch('providers.coverage_expansion.fetch_text', return_value=BODY) as fetch:
                self.assertEqual(run(root, strict=True), 0)
            fetch.assert_called_once_with(PUBLIC_SOURCES['arcee'].SOURCE)
            after_status = json.loads((root / 'status.json').read_text())
            self.assertEqual(next(p for p in before_status['providers'] if p['id'] == 'castform'),
                             next(p for p in after_status['providers'] if p['id'] == 'castform'))
            self.assertEqual(next(p for p in after_status['providers'] if p['id'] == 'arcee')['offering_count'], 3)
            for name, before in [('offerings.json', before_offers), ('latest_prices.json', before_prices)]:
                key = 'id' if name == 'offerings.json' else 'offering_id'
                self.assertEqual([r for r in before if r[key] in retained],
                                 [r for r in json.loads((root / name).read_text()) if r[key] in retained])
            self.assertEqual({json.loads(line)['provider'] for line in (root / 'collection_checks.jsonl').read_text().splitlines()}, {'arcee'})
            self.assertEqual(read_history(root / 'price_history.csv')[:len(before_history)], before_history)
            self.assertTrue(all(r['comparison_eligible'] is False for r in json.loads((root / 'provider_catalogs/arcee.json').read_text())['records']))
            self.assertFalse(any(c['provider'] == 'castform' or c['offering_id'] in retained for c in json.loads((root / 'changes.json').read_text()) if c['observed_at'] == after_status['last_run_at']))


if __name__ == '__main__':
    unittest.main()
