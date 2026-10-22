"""Public OpenAI layout regression and explicitly approved current 30m scope.

Fixtures/mutations are test inputs, never observations or historical TTL evidence.
"""
import copy
import hashlib
import unittest
from pathlib import Path

from providers import openai
from providers.common import Collection
from scripts.collect import apply_snapshot
from scripts.catalog_inventory import normalize_inventory
from scripts.normalize import catalog, normalize, price_signature

FIXTURES = Path(__file__).parent / 'fixtures'
BODY = (FIXTURES / 'openai-split-retention.md').read_text()
TIME = '2026-10-22T00:00:00Z'  # Test-only time, never persisted in production.
HASH = 'a' * 64


class OpenAILayoutTests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()
        self.scoped = self.aliases.for_provider('openai')

    def original_records(self):
        return (openai.parse((FIXTURES / 'openai.md').read_text(), self.aliases.legacy).records +
                openai.parse((FIXTURES / 'openai-reviewed-expansion.md').read_text(), self.aliases.sources['openai']).records)

    def test_split_retention_and_compact_tables_preserve_all_eleven_quote_identities_and_rates(self):
        actual = openai.parse(BODY, self.scoped).records
        expected = self.original_records()
        self.assertEqual(len(actual), 11)
        self.assertEqual({r['provider_model_id'] for r in actual}, set(openai.API_IDS.values()))
        def economic(rows):
            result = {}
            for row in rows:
                offering, price = normalize(row, self.aliases, TIME, HASH)
                offering.pop('pricing_notes')  # Current retention clarification is intentionally explicit.
                result[offering['id']] = (offering, price)
            return result
        self.assertEqual(economic(actual), economic(expected))
        for row in actual:
            if row['cache_write_per_million'] is not None:
                self.assertIn('30-minute', row['pricing_notes'])
                self.assertIn('12-hour', row['pricing_notes'])
                self.assertIn('Historical', row['pricing_notes'])
        mini = next(r for r in actual if r['provider_model_id'] == 'gpt-5.4-mini-2026-03-17')
        self.assertEqual((mini['min_input_tokens'], mini['max_input_tokens'], mini['variant']), (0, None, 'standard'))
        self.assertIsNone(mini['cache_write_per_million'])
        self.assertNotIn('gpt-5.6-sol', {r['provider_model_id'] for r in actual})

    def test_full_native_evidence_keeps_both_retention_columns_and_unreviewed_models(self):
        # Exclude the fixture-capture comment from the actual Markdown excerpt.
        native, _ = normalize_inventory('openai', BODY.split('-->', 1)[1], 'documentation')
        self.assertTrue(all(r['comparison_eligible'] is False for r in native['records']))
        astra = next(r for r in native['records'] if r['billing']['cells'][0] == 'gpt-6-astra' and
                     'Standard pricing data' in r['scope']['headings'])
        self.assertIn('Short context 30m write', astra['billing']['columns'])
        self.assertIn('Short context 12h write', astra['billing']['columns'])
        self.assertEqual(astra['billing']['cells'][4:6], ['$12.50', '$25.00'])
        self.assertTrue(any(r['billing']['cells'][0] == 'gpt-5.6-sol' for r in native['records']))

    def test_validated_column_names_not_positions_or_cheapest_retention_choose_rates(self):
        # Reorder complete header/cell pairs, keeping Model first.
        lines = []
        for line in BODY.splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if line.startswith('|') and len(cells) == 11:
                order = [0, 3, 8, 1, 9, 2, 4, 5, 6, 7, 10]
                line = '| ' + ' | '.join(cells[i] for i in order) + ' |'
            lines.append(line)
        self.assertEqual(openai.parse('\n'.join(lines), self.scoped).records, openai.parse(BODY, self.scoped).records)
        # The unreviewed 12-hour rate must not replace the approved 30m rate,
        # even in a test-only mutation where 12h happens to be cheaper.
        cheaper_12h = BODY.replace('| $2.50 | $5.00 | $4.00 |', '| $2.50 | $0.01 | $4.00 |')
        self.assertEqual(openai.parse(cheaper_12h, self.scoped).records, openai.parse(BODY, self.scoped).records)
        missing_30m = BODY.replace('| $2.50 | $5.00 | $4.00 |', '| - | $5.00 | $4.00 |')
        row = next(r for r in openai.parse(missing_30m, self.scoped).records if r['provider_model_id'] == 'gpt-6.1-sol' and r['min_input_tokens'] == 0)
        self.assertIsNone(row['cache_write_per_million'])

    def test_legacy_unqualified_cache_writes_are_not_relabelled_thirty_minutes(self):
        self.assertTrue(all('30-minute' not in r['pricing_notes'] for r in self.original_records()))

    def test_missing_unknown_duplicate_or_conflicting_headers_and_rows_fail_closed(self):
        row = next(l for l in BODY.splitlines() if l.startswith('| gpt-6-astra |'))
        broken = [BODY.replace('Short context 30m write', 'Short context write'),
                  BODY.replace('Long context 12h write', 'Long context 30m write'),
                  BODY.replace('Short context 12h write', 'Short context 24h write'),
                  BODY.replace(row, row.replace('| $50.00 |', '|', 1), 1),
                  BODY.replace(row, row + '\n' + row, 1),
                  BODY.replace(row, row + '\n' + row.replace('$10.00', '$9.00', 1), 1),
                  BODY.replace(row, row + '\n' + row.replace('| $50.00 |', '|', 1), 1)]
        for body in broken:
            with self.subTest(body=hashlib.sha256(body.encode()).hexdigest()), self.assertRaises(ValueError):
                openai.parse(body, self.scoped)

    def test_compact_table_cannot_extrapolate_a_known_long_context_model(self):
        body = 'Prices per 1M tokens.\n### Standard pricing data\n| Model | Input | Output | Cached input |\n| --- | --- | --- | --- |\n| gpt-6-astra | $10.00 | $50.00 | $1.00 |\n'
        with self.assertRaisesRegex(ValueError, 'long'):
            openai.parse(body, {'gpt-6-astra': self.scoped['gpt-6-astra']})

    def test_changed_or_unscoped_token_basis_boundary_and_invalid_rates_fail_closed(self):
        # A 1M statement in Batch cannot legitimize an ambiguous Standard basis.
        for body in (BODY.replace('Prices per 1M tokens.', 'Prices per 1K tokens.') + '\nPrices per 1M tokens.',
                     BODY.replace('Prices per 1M tokens.', '') + '\nPrices per 1M tokens.',
                     BODY.replace('Long context: >272K input tokens.', 'Long context: >200K input tokens.'),
                     BODY.replace('| $20.00 | $75.00 | $2.00 | $25.00 | $50.00 |', '| - | - | - | - | - |', 1),
                     BODY.replace('| $10.00 | $50.00 | $1.00 |', '| - | $50.00 | $1.00 |', 1),
                     BODY.replace('| $12.50 | $25.00 | $20.00 |', '| €12.50 | $25.00 | $20.00 |', 1)):
            with self.subTest(body=hashlib.sha256(body.encode()).hexdigest()), self.assertRaises(ValueError):
                openai.parse(body, self.scoped)

    def test_snapshot_keeps_history_and_ids_without_manufacturing_a_price_change(self):
        offerings, latest, history, changes = {}, {}, [], []
        previous = Collection(self.original_records(), openai.SOURCE, HASH)
        apply_snapshot('openai', previous, self.aliases, TIME, offerings, latest, history, changes)
        before_history = copy.deepcopy(history)
        before_ids = set(offerings)
        before_prices = {k: price_signature(v) for k, v in latest.items()}
        current = openai.parse(BODY, self.scoped)
        count = apply_snapshot('openai', current, self.aliases, '2026-10-22T01:00:00Z', offerings, latest, history, changes)
        self.assertEqual(count, 11)
        self.assertEqual(before_ids, set(offerings))
        self.assertEqual(before_prices, {k: price_signature(v) for k, v in latest.items()})
        self.assertEqual(before_history, history)
        self.assertFalse(any(e['kind'] == 'price_changed' for e in changes))
        stable = copy.deepcopy((offerings, latest, history, changes))
        bad = copy.deepcopy(current)
        bad.records.append(copy.deepcopy(bad.records[0]))
        with self.assertRaises(ValueError):
            apply_snapshot('openai', bad, self.aliases, '2026-10-22T02:00:00Z', offerings, latest, history, changes)
        self.assertEqual(stable, (offerings, latest, history, changes))


if __name__ == '__main__':
    unittest.main()
