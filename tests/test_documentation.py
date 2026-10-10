"""Cheap offline guards against mechanical README/documentation drift.

These checks do not replace reviewing whether prose matches changed behavior.
Counts are retained reviewed identities, not currently active/native record totals.
"""
import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / 'README.md'
AGENTS = ROOT / 'AGENTS.md'
TEMPLATE = ROOT / '.github/pull_request_template.md'


def markdown_links(text):
    # Ignore example code blocks; inline links/images in prose use normal Markdown syntax.
    prose = re.sub(r'^```[^\n]*\n.*?^```\s*$', '', text, flags=re.M | re.S)
    return re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', prose)


def heading_ids(text):
    ids, repeated = set(), {}
    for line in text.splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)
        if not match:
            continue
        slug = re.sub(r'[^\w\s-]', '', match[1].lower()).replace(' ', '-')
        count = repeated.get(slug, 0)
        repeated[slug] = count + 1
        ids.add(slug if not count else '{}-{}'.format(slug, count))
    return ids


def local_link_errors(path):
    errors = []
    for link in markdown_links(path.read_text()):
        # This project uses unquoted Markdown destinations without optional titles.
        value = urlsplit(link.strip('<>'))
        if value.scheme or value.netloc:
            continue
        target = (path.parent / unquote(value.path)).resolve() if value.path else path
        if not target.exists():
            errors.append('{}: missing {}'.format(path.relative_to(ROOT), link))
            continue
        if value.fragment and target.suffix.lower() == '.md':
            if unquote(value.fragment) not in heading_ids(target.read_text()):
                errors.append('{}: missing heading {}'.format(path.relative_to(ROOT), link))
    return errors


class DocumentationTests(unittest.TestCase):
    def test_local_documentation_links_and_fragments_resolve(self):
        documents = [README, AGENTS, TEMPLATE] + sorted((ROOT / 'docs').glob('*.md'))
        errors = [error for path in documents for error in local_link_errors(path)]
        self.assertEqual(errors, [], '\n'.join(errors))

    def test_advertised_npm_commands_exist(self):
        scripts = json.loads((ROOT / 'package.json').read_text())['scripts']
        docs = [README, AGENTS, TEMPLATE] + sorted((ROOT / 'docs').glob('*.md'))
        for path in docs:
            commands = set(re.findall(r'\bnpm run ([a-z][a-z0-9:_-]*)', path.read_text()))
            for command in commands:
                with self.subTest(path=str(path.relative_to(ROOT)), command=command):
                    self.assertIn(command, scripts, 'Update the command/docs together, not by skipping this check.')

    def test_readme_reviewed_baseline_counts_retained_not_only_active_offerings(self):
        readme = README.read_text()
        declared = re.search(
            r'Reviewed baseline:\s*\*\*(\d+) canonical models / (\d+) recorded offerings / (\d+) reviewed providers\*\*',
            readme,
        )
        self.assertIsNotNone(declared, 'Keep a clearly labeled reviewed baseline in README.md.')
        models = json.loads((ROOT / 'data/models.json').read_text())
        offerings = json.loads((ROOT / 'data/offerings.json').read_text())
        expected = (len(models), len(offerings), len({row['provider'] for row in offerings}))
        self.assertEqual(tuple(map(int, declared.groups())), expected,
                         'Update the README baseline when retained coverage changes; do not rewrite data to fit prose.')
        self.assertIn('including inactive offerings', readme.lower())
        self.assertIn('data/offerings.json', readme)
        self.assertIn('data/status.json', readme)

    def test_readme_collection_scope_matches_committed_provider_index(self):
        declared = re.search(r'Collection scope:\s*\*\*(\d+) provider groups\*\*', README.read_text())
        self.assertIsNotNone(declared, 'Label collected provider groups separately from reviewed providers.')
        inventory = json.loads((ROOT / 'data/provider_inventory.json').read_text())
        self.assertEqual(int(declared.group(1)), inventory['provider_count'],
                         'Update README collection scope when provider groups change.')
        self.assertEqual(inventory['provider_count'], len(inventory['providers']))

    def test_all_workflows_and_activation_gates_are_documented(self):
        readme = README.read_text()
        for path in sorted((ROOT / '.github/workflows').glob('*.yml')):
            with self.subTest(workflow=path.name):
                self.assertIn(path.name, readme)
                gates = set(re.findall(r'\bvars\.(ENABLE_[A-Z_]+)', path.read_text()))
                for gate in gates:
                    self.assertIn(gate, readme, 'Document new activation gates in the same change.')

    def test_readme_documents_generated_native_assets_not_just_reviewed_files(self):
        readme = README.read_text()
        self.assertIn('scripts/dashboard_projection.ts', readme)
        projection = (ROOT / 'scripts/dashboard_projection.ts').read_text()
        static_assets = set(re.findall(r"put\(['\"](catalog/(?:index|models)\.json)['\"]", projection))
        self.assertTrue(static_assets)
        for asset in static_assets:
            self.assertIn(asset, readme)
        for prefix in ['catalog/providers/', 'catalog/history/', 'catalog/changes/']:
            self.assertIn(prefix, readme)
        self.assertIn('not committed', readme)

    def test_contributor_entry_points_include_readme_maintenance(self):
        readme, agents, template = README.read_text(), AGENTS.read_text(), TEMPLATE.read_text()
        self.assertIn('[AGENTS.md](AGENTS.md)', readme)
        self.assertIn('## Documentation and maintenance', readme)
        self.assertIn('Documentation maintenance contract', agents)
        self.assertIn('same commit/PR', agents)
        self.assertIn('reason no README update is needed', template)
        self.assertIn('same commit/PR', readme)


if __name__ == '__main__':
    unittest.main()
