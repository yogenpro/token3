"""November source enrollment: exact identities, conditions and failure retention."""
import copy
import hashlib
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from providers import anthropic, deepinfra, gemini, meta, mistral, moonshot, openai
from providers.comparison_expansion import expanded_quotes
from providers.markdoc import table_markdown
from scripts.catalog_inventory import normalize_inventory
from scripts.collect import apply_snapshot
from scripts.normalize import catalog, normalize

FIXTURES = Path(__file__).parent / 'fixtures' / 'usagepricing-review'
TIME = '2026-11-04T00:00:00Z'  # Fixture-only timestamp, never production data.
HASH = 'a' * 64


def body(provider):
    return (FIXTURES / (provider + ('.html.txt' if provider == 'moonshot' else '.json' if provider == 'deepinfra' else '.md'))).read_text()


class CoverageReviewTests(unittest.TestCase):
    def setUp(self):
        self.models, self.aliases = catalog()

    def rows(self, provider, text=None, **kwargs):
        text = body(provider) if text is None else text
        if provider in ('xai', 'zai', 'alibaba'):
            return expanded_quotes(provider, {'documents': [{'body': text}]},
                                   self.aliases.for_provider(provider), 'https://example.com/pricing')
        return globals()[provider].parse(text, self.aliases, **kwargs).records

    def test_every_new_identity_has_a_bound_complete_normalizable_quote(self):
        added = set(json.loads((FIXTURES / 'new-model-ids.json').read_text()))
        self.assertEqual(len(added), 58)
        baseline = json.loads((FIXTURES.parent / 'reviewed-bindings-2026-10-26.json').read_text())
        self.assertEqual({m['id'] for m in self.models}, set(baseline['model_ids']) | added)
        records = [r for p in ('openai', 'anthropic', 'gemini', 'mistral', 'meta', 'moonshot', 'xai', 'zai', 'alibaba', 'deepinfra') for r in self.rows(p)]
        normalized = [normalize(r, self.aliases, TIME, HASH)[0] for r in records]
        self.assertEqual({o['model_id'] for o in normalized} & added, added)
        self.assertEqual(len({o['id'] for o in normalized}), len(normalized))
        for provider, bindings in baseline['sources'].items():
            self.assertLessEqual(bindings.items(), self.aliases.for_provider(provider).items())
        self.assertNotIn('gpt-6.1-terra', self.aliases.for_provider('vertex'))
        self.assertNotIn('muse-spark-1.3-contributor', self.aliases)
        self.assertNotIn('kimi-k2.7-code-highspeed', self.aliases)
        self.assertNotEqual(self.aliases['gpt-5.5'], self.aliases['gpt-5.5-pro'])

    def test_public_fixture_excerpts_have_independent_hashes_and_bounds(self):
        manifest = json.loads((FIXTURES / 'manifest.json').read_text())
        for info in manifest['sources'].values():
            b = (FIXTURES / info['file']).read_bytes()
            self.assertEqual(len(b), info['excerpt_bytes'])
            self.assertEqual(hashlib.sha256(b).hexdigest(), info['excerpt_sha256'])
            self.assertLess(len(b), 128 * 1024)

    def test_openai_complete_long_bands_and_thirty_minute_writes(self):
        rows = self.rows('openai')
        terra = [r for r in rows if r['provider_model_id'] == 'gpt-6.1-terra']
        self.assertEqual([(r['input_per_million'], r['output_per_million'], r['cache_write_per_million']) for r in terra], [(1, 5, 1.25), (2, 7.5, 2.5)])
        self.assertEqual([(r['min_input_tokens'], r['max_input_tokens']) for r in terra], [(0, 272000), (272001, None)])
        row = next(line for line in body('openai').splitlines() if line.startswith('| gpt-6.1-terra |'))
        for bad in (body('openai').replace(row, ''), body('openai').replace(row, row + '\n' + row), body('openai').replace('Prices per 1M tokens.', 'Prices per 1K tokens.')):
            with self.assertRaises(ValueError): self.rows('openai', bad)

    def test_markdoc_matches_existing_review_and_preserves_original_source_hash(self):
        parsed = gemini.parse(body('gemini'), self.aliases, as_of=date(2026, 11, 4))
        self.assertEqual(parsed.source_sha256, hashlib.sha256(body('gemini').encode()).hexdigest())
        native, _ = normalize_inventory('gemini', body('gemini'), 'documentation')
        self.assertTrue(native['records'])
        self.assertTrue(all(not r['comparison_eligible'] for r in native['records']))
        argon = next(r for r in parsed.records if r['provider_model_id'] == 'gemini-4-argon')
        self.assertEqual((argon['input_per_million'], argon['output_per_million'], argon['cache_read_per_million']), (2, 10, .1))
        future = self.rows('gemini', as_of=date(2026, 12, 1))
        argon = next(r for r in future if r['provider_model_id'] == 'gemini-4-argon')
        self.assertEqual((argon['input_per_million'], argon['output_per_million']), (4, 20))
        flash = next(r for r in parsed.records if r['provider_model_id'] == 'gemini-2.5-flash')
        self.assertEqual((flash['input_per_million'], flash['cache_read_per_million']), (.3, .03))
        pro = [r for r in parsed.records if r['provider_model_id'] == 'gemini-2.5-pro']
        self.assertEqual([(r['min_input_tokens'], r['max_input_tokens']) for r in pro], [(0, 200000), (200001, None)])
        for bad in (body('gemini').replace('  * $0.75 through December 31, 2026.', '  $0.75 through December 31, 2026.', 1), body('gemini').replace('{% /table %}', '', 1)):
            with self.assertRaises(ValueError): table_markdown(bad)

    def test_mistral_no_cache_fallback_or_non_token_conversion(self):
        rows = self.rows('mistral')
        small = next(r for r in rows if r['provider_model_id'] == 'mistral-small-2603')
        self.assertIsNone(small['cache_read_per_million'])
        self.assertIsNone(small['context_window'])
        for old, new in [('/M Tokens', '/Min'), ('`codestral-2508`', '`unreviewed-latest`'), ('| API name |', '| Endpoint |')]:
            with self.assertRaises(ValueError): self.rows('mistral', body('mistral').replace(old, new))
        with patch.object(mistral, 'fetch_text', side_effect=[body('mistral'), '<button aria-pressed="true">EUR</button><button aria-pressed="true">Standard</button>']):
            with self.assertRaises(ValueError): mistral.collect(self.aliases)

    def test_meta_contributor_prices_never_substitute_for_standard(self):
        rows = self.rows('meta')
        spark = next(r for r in rows if r['provider_model_id'] == 'muse-spark-1.3')
        self.assertEqual((spark['input_per_million'], spark['output_per_million']), (1.25, 4.25))
        self.assertEqual(self.rows('meta', body('meta').replace('$0.10', '$0.001')), rows)
        for old, new in [('Standard mode (per 1M tokens)', 'Standard mode (per 1K tokens)'), ('`muse-spark-1.1` in Standard mode', '`muse-spark-1.1` in Contributor mode')]:
            with self.assertRaises(ValueError): self.rows('meta', body('meta').replace(old, new))

    def test_kimi_inert_tables_cache_ttl_and_access_limits(self):
        rows = self.rows('moonshot')
        k3 = next(r for r in rows if r['provider_model_id'] == 'kimi-k3')
        self.assertEqual((k3['input_per_million'], k3['cache_write_per_million'], k3['context_window']), (3, 3, 1048576))
        self.assertTrue(all('existing users' in r['pricing_notes'] for r in rows))
        native, _ = normalize_inventory('moonshot', body('moonshot'), 'documentation')
        self.assertEqual(len(native['records']), 6)
        self.assertTrue(all(not r['comparison_eligible'] for r in native['records']))
        self.assertTrue(any(r['native_id'] == 'kimi-k3.1-pro-highspeed' for r in native['records']))
        self.assertTrue(any('existing users are not affected' in note for note in native['billing_notes']))
        for old, new in [('`$3.00 / MTok`', '`$3.00 / hour`'), ('title:`Input`', 'title:`Output`'), ('children:`kimi-k3`', 'children:`unreviewed-kimi`'), ('December 2026', 'January 2027')]:
            with self.assertRaises(ValueError): self.rows('moonshot', body('moonshot').replace(old, new))

    def test_direct_qwen_scope_and_long_grok_bands_remain_explicit(self):
        qwen = [r for r in self.rows('alibaba') if r['provider_model_id'] == 'qwen3.8-max'][0]
        self.assertEqual((qwen['input_per_million'], qwen['output_per_million'], qwen['min_input_tokens'], qwen['max_input_tokens']), (2, 6, 1, 1000000))
        with self.assertRaises(ValueError): self.rows('alibaba', body('alibaba').replace('0\\<Token≤1M', '0\\<Token≤256K'))
        plus = [r for r in self.rows('alibaba') if r['provider_model_id'] == 'qwen3.7-plus']
        self.assertEqual([(r['input_per_million'], r['output_per_million']) for r in plus], [(.32, 1.28), (.32, 1.28), (.96, 3.84), (.96, 3.84)])
        self.assertEqual({r['variant'] for r in plus}, {'thinking', 'non-thinking'})
        with self.assertRaises(ValueError): self.rows('alibaba', body('alibaba').replace('Limited-time 20% off', 'Limited-time 30% off'))
        with self.assertRaises(ValueError): self.rows('alibaba', body('alibaba').replace('K means 1,000', 'K means 1,024'))
        grok = [r for r in self.rows('xai') if r['provider_model_id'] == 'grok-4.6']
        self.assertEqual([(r['input_per_million'], r['max_input_tokens']) for r in grok], [(2, 199999), (4, None)])
        with self.assertRaises(ValueError): self.rows('xai', body('xai').replace('grok-4.6 (≥ 200k prompt tokens)', 'grok-4.6 (≥ 256k prompt tokens)'))
        hosted = self.rows('deepinfra')
        self.assertEqual({r['provider_model_id'] for r in hosted}, {'Qwen/Qwen3.7-Max'})
        self.assertTrue(all(normalize(r, self.aliases, TIME, HASH)[0]['model_id'] == 'qwen/qwen3.7-max' for r in hosted))
        native, _ = normalize_inventory('alibaba', json.dumps({'format': 'token3.inventory-sources.v1', 'adapter': 'documents',
            'documents': [{'source_url': 'https://example.com/pricing', 'body': body('alibaba')}]}), 'documentation')
        source_cells = [cell for r in native['records'] for cell in r['billing']['cells']]
        self.assertIn('0<Token≤1M', source_cells)
        self.assertIn('32K<Token≤256K', source_cells)
        self.assertTrue(all(not r['comparison_eligible'] for r in native['records']))

    def test_failure_retains_all_previous_reviewed_observations(self):
        valid = meta.parse(body('meta'), self.aliases)
        offerings, latest, history, changes = {}, {}, [], []
        apply_snapshot('meta', valid, self.aliases, TIME, offerings, latest, history, changes)
        before = copy.deepcopy((offerings, latest, history, changes))
        invalid = copy.deepcopy(valid)
        invalid.records.append(copy.deepcopy(valid.records[0]))
        with self.assertRaises(ValueError): apply_snapshot('meta', invalid, self.aliases, TIME, offerings, latest, history, changes)
        self.assertEqual((offerings, latest, history, changes), before)

    def test_dated_audit_accounts_for_hidden_rows_and_unresolved_source_boundaries(self):
        report = json.loads((FIXTURES.parents[2] / 'docs/research/usagepricing-gap-review-2026-11-04.json').read_text())
        rows = report['rows']
        self.assertEqual(len(rows), 146)
        self.assertEqual(len({r['usagepricing_slug'] for r in rows}), 146)
        self.assertEqual(sum(r['usagepricing_status'] == 'deprecated' for r in rows), 19)
        self.assertEqual(sum(report['summary']['dispositions'].values()), len(rows))
        self.assertTrue(all(r['disposition'] == 'operator_paused' for r in rows if r['collector_id'] == 'together'))
        self.assertTrue(all(r['canonical_id'] is None for r in rows if r['usagepricing_provider_slug'] == 'zhipu'))
        offerings = {o['id']: o for o in json.loads((FIXTURES.parents[2] / 'data/offerings.json').read_text())}
        for row in rows:
            if row['disposition'] == 'reviewed_source_covered':
                self.assertTrue(row['after_reviewed_active_offering_ids'])
                self.assertTrue(all(offerings[oid]['provider'] == row['collector_id'] and offerings[oid]['model_id'] == row['canonical_id']
                                    for oid in row['after_reviewed_active_offering_ids']))


if __name__ == '__main__':
    unittest.main()
