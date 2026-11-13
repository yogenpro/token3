"""Public-source layout regressions and unresolved-source retention for issue 35."""
import copy
import hashlib
import json
import unittest
from pathlib import Path

from providers import moonshot
from providers.comparison_expansion import ovhcloud_quotes
from providers.coverage_quotes import reviewed_quotes
from scripts.catalog_inventory import normalize_inventory
from scripts.normalize import catalog

FIXTURES = Path(__file__).parent / 'fixtures'
CAPTURES = FIXTURES / 'issue-35'


class Issue35Tests(unittest.TestCase):
    def setUp(self):
        _, self.aliases = catalog()

    def test_capture_provenance(self):
        manifest = json.loads((CAPTURES / 'manifest.json').read_text())
        for file, info in manifest['sources'].items():
            body = (CAPTURES / file).read_bytes()
            self.assertEqual(len(body), info['excerpt_bytes'])
            self.assertEqual(hashlib.sha256(body).hexdigest(), info['excerpt_sha256'])
            self.assertLess(len(body), 128 * 1024)

    def test_kimi_plain_k2_labels_preserve_reviewed_and_native_records(self):
        before = (FIXTURES / 'provider-coverage-review/moonshot.html.txt').read_text()
        after = (CAPTURES / 'moonshot.html.txt').read_text()
        self.assertEqual(moonshot.parse(after, self.aliases).records,
                         moonshot.parse(before, self.aliases).records)
        native, _ = normalize_inventory('moonshot', after, 'documentation')
        old_native, _ = normalize_inventory('moonshot', before, 'documentation')
        self.assertEqual(native['records'], old_native['records'])
        self.assertTrue(all(r['comparison_eligible'] is False for r in native['records']))

    def test_kimi_plain_labels_still_fail_closed(self):
        body = (CAPTURES / 'moonshot.html.txt').read_text()
        for old, new in [
            ('[`kimi-k2.6`,', '[`unknown-kimi`,'),
            ('[`kimi-k2.6`,', '[`kimi-k2.7-code`,'),
            ('[`kimi-k2.6`,', '[getModel(),'),
            ('[`kimi-k2.6`,', '[`kimi-${run()}`,'),
            ('`$0.95 / MTok`', '`$0.95 / hour`'),
            ('title:`Input`', 'title:`Output`'),
            ('December 2026', 'January 2027'),
        ]:
            with self.subTest(change=(old, new)), self.assertRaises(ValueError):
                moonshot.parse(body.replace(old, new), self.aliases)

    def ovh_quotes(self, body):
        source = 'https://www.ovhcloud.com/en/public-cloud/ai-endpoints/catalog/'
        return ovhcloud_quotes({'reviewed_price_cards': {'source_url': source, 'body': body}},
                               self.aliases.for_provider('ovhcloud'), source)

    def test_ovh_prefix_euro_preserves_every_reviewed_field(self):
        before = json.loads((FIXTURES / 'provider-comparisons/ovhcloud.json').read_text())
        body = (CAPTURES / 'ovhcloud.html').read_text()
        self.assertEqual(self.ovh_quotes(body), self.ovh_quotes(before['reviewed_price_cards']['body']))

    def test_ovh_prefix_euro_rejects_changed_scope_and_ambiguity(self):
        body = (CAPTURES / 'ovhcloud.html').read_text()
        for bad in [body.replace('€', '$'), body.replace('Mtoken', 'Ktoken'),
                    body.replace('(input)', '(output)'), body + body,
                    body.replace('€0.08', '0.08'), body.replace('€0.08', '€-0.08'),
                    body.replace('€0.08', '€0.08€')]:
            with self.subTest(source=bad), self.assertRaises(ValueError):
                self.ovh_quotes(bad)

    def test_arcee_missing_tracked_ids_remain_a_strict_failure(self):
        body = (CAPTURES / 'arcee.md').read_text()
        payload = {'documents': [{'source_url': 'https://docs.arcee.ai/get-started/pricing.md', 'body': body}]}
        with self.assertRaisesRegex(ValueError, 'Tracked model.*missing.*deepseek/deepseek-v4-pro-0813.*zai-org/glm-5.2'):
            reviewed_quotes('arcee', copy.deepcopy(payload), self.aliases)


if __name__ == '__main__':
    unittest.main()
