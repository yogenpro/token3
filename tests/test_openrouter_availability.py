"""Complete public gateway listings can change without deleting quote history."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from providers.expanded import INVENTORY_PROVIDERS
from providers.reviewed_inventory import reviewed_quotes
from scripts.collect import apply_snapshot
from scripts.normalize import catalog

FIXTURES = Path(__file__).parent / 'fixtures'
SOURCE = INVENTORY_PROVIDERS['openrouter'].SOURCE
TIME = '2026-11-05T14:41:11Z'  # Fixture time, not a production write.


def capture():
    return json.loads((FIXTURES / 'openrouter-availability-2026-11-05.json').read_text())


class OpenRouterAvailabilityTests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()

    def collect(self, payload=None, collector=None):
        body = (payload or capture())['catalog']
        with patch('providers.expanded.fetch_text', return_value=json.dumps(body)) as fetch:
            result = (collector or INVENTORY_PROVIDERS['openrouter']).collect(self.aliases)
        fetch.assert_called_once_with(SOURCE)
        return result

    def test_failed_run_capture_accepts_complete_catalog_with_two_absent_bindings(self):
        payload = capture()
        result = self.collect(payload)
        self.assertIsNone(result.parse_error)
        self.assertTrue(result.authoritative_catalog)
        self.assertEqual(len(result.records), 62)
        missing = set(self.aliases.for_provider('openrouter')) - {r['provider_model_id'] for r in result.records}
        self.assertEqual(missing, {'minimax/minimax-m2', 'minimax/minimax-m2.1'})
        # Every remaining quote uses precisely the captured fields and amounts.
        complete = copy.deepcopy(payload)
        missing_rows = [row for path in sorted((FIXTURES / 'provider-model-expansion').glob('openrouter-*.json'))
                        for row in json.loads(path.read_text())['data'] if row['id'] in missing]
        self.assertEqual(len(missing_rows), 2)
        complete['catalog']['data'].extend(missing_rows)
        complete['catalog']['total_count'] += len(missing_rows)
        before = reviewed_quotes('openrouter', complete, self.aliases, SOURCE)
        self.assertEqual(result.records, [r for r in before if r['provider_model_id'] not in missing])

    def test_missing_metadata_partial_duplicate_private_or_empty_catalogs_fail_closed(self):
        changes = [lambda c: c.pop('total_count'), lambda c: c.pop('links'),
                   lambda c: c.update(total_count=True), lambda c: c.update(total_count=float(c['total_count'])),
                   lambda c: c.update(total_count=c['total_count'] + 1), lambda c: c.update(links={}),
                   lambda c: c.update(links={'next': '/api/v1/models?offset=452'}),
                   lambda c: c.update(has_more=True), lambda c: c.update(nextPageToken='next'),
                   lambda c: c['data'].append(copy.deepcopy(c['data'][0])),
                   lambda c: c['data'][-1].update(id=c['data'][0]['id']),
                   lambda c: c['data'][-1].update(id=''), lambda c: c['data'][-1].update(private=True),
                   lambda c: c.update(data=[], total_count=0)]
        for index, change in enumerate(changes):
            payload = capture()
            change(payload['catalog'])
            with self.subTest(index=index), self.assertRaises((ValueError, KeyError)):
                self.collect(payload)

    def test_absence_does_not_relax_economic_or_empty_reviewed_snapshot_checks(self):
        for change in ('conditional', 'currency', 'modality', 'missing_rate', 'no_reviewed'):
            payload = capture()
            rows = payload['catalog']['data']
            target = next(r for r in rows if r['id'] == 'openai/gpt-oss-120b')
            if change == 'conditional': target['pricing']['request'] = '.01'
            elif change == 'currency': target['currency'] = 'EUR'
            elif change == 'modality': target['architecture']['output_modalities'] = ['image']
            elif change == 'missing_rate': target['pricing'].pop('prompt')
            else:
                payload['catalog']['data'] = [r for r in rows if r['id'] not in self.aliases.for_provider('openrouter')]
                payload['catalog']['total_count'] = len(payload['catalog']['data'])
            with self.subTest(change=change):
                result = self.collect(payload)
                self.assertIsNotNone(result.parse_error)
                self.assertFalse(result.authoritative_catalog)
                self.assertEqual(result.records, [])

    def test_filtered_or_other_source_cannot_authorize_absence(self):
        for source in (SOURCE + '?output_modalities=text', 'https://example.com/models'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                reviewed_quotes('openrouter', capture(), self.aliases, source)
        # Other adapters retain their complete tracked-binding requirement.
        payload = json.loads((FIXTURES / 'provider-comparisons/huggingface.json').read_text())
        payload['catalog']['data'].pop()
        with self.assertRaises(ValueError):
            reviewed_quotes('huggingface', payload, self.aliases, INVENTORY_PROVIDERS['huggingface'].SOURCE)

    def test_removal_and_return_preserve_original_offerings_prices_and_history(self):
        payload = capture()
        result = self.collect(payload)
        missing = {'minimax/minimax-m2', 'minimax/minimax-m2.1'}
        restored = copy.deepcopy(payload)
        for path in sorted((FIXTURES / 'provider-model-expansion').glob('openrouter-*.json')):
            restored['catalog']['data'].extend(r for r in json.loads(path.read_text())['data'] if r['id'] in missing)
        restored['catalog']['total_count'] = len(restored['catalog']['data'])
        original = self.collect(restored)
        offerings, latest, history, events = {}, {}, [], []
        apply_snapshot('openrouter', original, self.aliases, '2026-11-04T00:00:00Z', offerings, latest, history, events)
        # Another billing source for a missing model must remain untouched.
        other = dict(copy.deepcopy(next(iter(offerings.values()))), id='other-provider', provider='novita')
        offerings[other['id']] = other
        before_offerings, before_latest, before_history = copy.deepcopy(offerings), copy.deepcopy(latest), copy.deepcopy(history)
        events.clear()
        apply_snapshot('openrouter', result, self.aliases, TIME, offerings, latest, history, events)
        removed = [o for o in offerings.values() if not o['active']]
        self.assertEqual({o['provider_model_id'] for o in removed}, missing)
        self.assertEqual({(e['kind'], e['offering_id']) for e in events}, {('offering_removed', o['id']) for o in removed})
        self.assertEqual(offerings['other-provider'], other)
        self.assertEqual(history, before_history)
        for o in removed:
            self.assertEqual(o, dict(before_offerings[o['id']], active=False))
            self.assertEqual(latest[o['id']], before_latest[o['id']])
        events.clear()
        apply_snapshot('openrouter', result, self.aliases, TIME, offerings, latest, history, events)
        self.assertEqual(events, [])
        apply_snapshot('openrouter', original, self.aliases, '2026-11-06T00:00:00Z', offerings, latest, history, events)
        self.assertEqual({(e['kind'], e['offering_id']) for e in events}, {('offering_restored', o['id']) for o in removed})
        self.assertTrue(all(o['active'] for o in offerings.values()))
        self.assertEqual(history, before_history)

    def test_fixture_has_exact_source_provenance_and_bounded_reduction(self):
        raw = (FIXTURES / 'openrouter-availability-2026-11-05.json').read_bytes()
        provenance = json.loads((FIXTURES / 'openrouter-availability-provenance.json').read_text())
        self.assertEqual(len(raw), provenance['fixture_bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), provenance['fixture_sha256'])
        self.assertRegex(provenance['parent_source_sha256'], r'^[a-f0-9]{64}$')
        self.assertNotEqual(provenance['parent_source_sha256'], provenance['fixture_sha256'])
        self.assertLess(len(raw), 256 * 1024)
        self.assertEqual(provenance['source_url'], SOURCE)


if __name__ == '__main__':
    unittest.main()
