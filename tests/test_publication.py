"""Publication policy tests, including actual temporary Git trees (no deployments)."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import resolve_publication as publication


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.real_run = subprocess.run
        self.git('init')
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        (self.root / 'data').mkdir()
        (self.root / 'README.md').write_text('reviewed release\n')
        (self.root / 'data/status.json').write_text('{}\n')
        self.baseline = self.commit()
        (self.root / 'data/status.json').write_text('{"updated":true}\n')
        self.target = self.commit()

    def git(self, *args):
        return self.real_run(['git', *args], cwd=self.root, text=True, capture_output=True, check=True).stdout.strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-m', 'test-only tree')
        return self.git('rev-parse', 'HEAD')

    def api(self, path):
        if path.endswith('/git/ref/heads/main'):
            return {'object': {'sha': self.target}}
        if '/statuses?' in path:
            return [{'state': 'success'}]
        return [{'id': 1, 'environment': 'github-pages', 'sha': self.baseline}]

    def resolve(self, target=None, api=None):
        def run(*args, **kwargs):
            return self.real_run(*args, cwd=self.root, **kwargs)
        with patch.object(publication, 'api', side_effect=api or self.api), patch.object(publication.subprocess, 'run', side_effect=run):
            return publication.resolve('owner/repo', 'refs/heads/main', self.baseline, target or self.target)

    def test_manual_release_is_pinned_without_querying_an_automatic_baseline(self):
        with patch.object(publication, 'api') as api:
            result = publication.resolve('owner/repo', 'refs/heads/main', self.baseline)
        self.assertEqual(result['sha'], self.baseline)
        self.assertEqual(result['mode'], 'manual')
        api.assert_not_called()

    def test_automatic_release_accepts_only_the_exact_data_only_git_tree(self):
        result = self.resolve()
        self.assertTrue(result['publish'])
        self.assertEqual(result['sha'], self.target)
        self.assertEqual(result['mode'], 'automatic')

    def test_unpublished_code_docs_or_workflow_changes_block_automatic_release(self):
        for name in ['README.md', 'scripts/new.py', '.github/workflows/new.yml']:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('not yet released\n')
            self.target = self.commit()
            result = self.resolve()
            self.assertFalse(result['publish'], name)
            self.assertIn('manual release', result['reason'])

    def test_superseded_snapshot_is_not_published(self):
        previous = self.target
        (self.root / 'data/status.json').write_text('{"newer":true}\n')
        self.target = self.commit()
        self.assertFalse(self.resolve(previous)['publish'])

    def test_unknown_baseline_and_rollback_fail_closed(self):
        def missing(path):
            return {'object': {'sha': self.target}} if '/git/ref/' in path else []
        self.assertFalse(self.resolve(api=missing)['publish'])
        old_target = self.baseline
        self.baseline = self.target
        self.target = old_target
        self.assertFalse(self.resolve()['publish'])

    def test_invalid_inputs_and_non_main_refs_are_rejected_without_execution(self):
        for repo, ref, sha in [('owner/repo', 'refs/heads/pr', self.target), ('owner/repo', 'refs/heads/main', '$(echo unsafe)'), ('owner/repo/extra', 'refs/heads/main', self.target)]:
            with self.subTest(ref=ref, sha=sha), patch.object(publication, 'api') as api, self.assertRaises(ValueError):
                publication.resolve(repo, ref, self.baseline, sha)
            api.assert_not_called()

    def test_deployment_checks_accept_prior_success_but_not_pending_or_failure(self):
        with patch.object(publication, 'api', side_effect=[[{'id': 1, 'environment': 'github-pages', 'sha': self.baseline}], [{'state': 'inactive'}, {'state': 'success'}]]):
            self.assertEqual(publication.latest_successful_deployment('owner/repo'), self.baseline)
        with patch.object(publication, 'api', side_effect=[[{'id': 1, 'environment': 'github-pages', 'sha': self.baseline}], [{'state': 'failure'}]]):
            self.assertIsNone(publication.latest_successful_deployment('owner/repo'))


if __name__ == '__main__':
    unittest.main()
