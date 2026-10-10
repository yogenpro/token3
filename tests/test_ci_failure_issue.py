"""Failure-ticket provenance, handoffs, redaction, bounded downloads and GitHub writes."""
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import yaml

from scripts import ci_failure_issue as tickets

ROOT = Path(__file__).resolve().parent.parent


class FakeGitHub:
    def __init__(self, collection=False):
        self.repo = {'full_name': 'owner/repo', 'default_branch': 'main',
                     'owner': {'type': 'User', 'login': 'owner'}}
        self.run = {'id': 123, 'run_attempt': 1, 'workflow_id': 22 if collection else 11,
                    'head_repository': {'full_name': 'owner/repo'}, 'head_branch': 'main',
                    'event': 'schedule' if collection else 'push', 'status': 'completed',
                    'conclusion': 'failure', 'head_sha': 'a' * 40,
                    'path': '.github/workflows/collect.yml' if collection else '.github/workflows/ci.yml',
                    'created_at': '2026-10-09T06:17:00Z'}
        self.jobs = [{'id': 456, 'name': 'collect' if collection else 'check', 'conclusion': 'failure',
                      'check_run_url': 'https://api.github.com/repos/owner/repo/check-runs/789',
                      'steps': [{'name': 'Surface collector failures' if collection else 'npm run check',
                                 'conclusion': 'failure'}]}]
        self.annotations = [{'annotation_level': 'failure', 'path': 'tests/test_public_pricing.py',
                             'start_line': 42, 'message': 'AssertionError: expected 15 quotes, got 0'}]
        self.artifacts = []
        self.issues = []
        self.labels = []
        self.writes = []
        self.reads = []
        self.changed = None
        self.run_reads = 0
        self.logs = b'2026-10-09T06:18:00Z FAIL tests/test_public_pricing.py\nAssertionError: expected 15 quotes, got 0\n'
        self.context = {'schema_version': 1, 'failed_run_id': '123', 'run_attempt': '1',
                        'last_run_at': '2026-10-09T06:17:10Z',
                        'failed_providers': [{'id': 'vertex', 'error': 'curated parser failed: tracked models missing'}]}
        self.archive = None

    def add_context(self):
        self.artifacts = [{'id': 999, 'name': 'self-heal-context-123-1', 'expired': False, 'size_in_bytes': 500}]

    def api(self, path, method='GET', body=None, binary=False):
        if method != 'GET':
            self.writes.append((path, method, copy.deepcopy(body)))
            if path == '/issues' and method == 'POST':
                issue = dict(body, number=len(self.issues) + 1, state='open', user={'login': tickets.BOT})
                self.issues.append(issue)
                return copy.deepcopy(issue)
            if path.startswith('/issues/') and method == 'PATCH':
                number = int(path.rsplit('/', 1)[-1])
                issue = next(i for i in self.issues if i['number'] == number)
                issue.update(body)
                return copy.deepcopy(issue)
            if path == '/labels':
                self.labels.append(body)
                return body
            raise AssertionError('Unexpected GitHub write: ' + path)
        self.reads.append(path)
        if path == '':
            return copy.deepcopy(self.repo)
        if path == '/actions/runs/123':
            self.run_reads += 1
            value = self.changed if self.run_reads > 1 and self.changed else self.run
            return copy.deepcopy(value)
        if path == '/actions/workflows/ci.yml':
            return {'id': 11}
        if path == '/actions/workflows/collect.yml':
            return {'id': 22}
        if '/attempts/' in path and '/jobs?' in path:
            return {'total_count': len(self.jobs), 'jobs': copy.deepcopy(self.jobs)}
        if path.startswith('/check-runs/'):
            return copy.deepcopy(self.annotations)
        if path.startswith('/actions/runs/') and '/artifacts?' in path:
            return {'artifacts': copy.deepcopy(self.artifacts)}
        if path.startswith('/issues?'):
            return copy.deepcopy(self.issues)
        if path == '/labels?per_page=100':
            return copy.deepcopy(self.labels)
        raise AssertionError('Unexpected GitHub read: ' + path)

    def download(self, path, limit=tickets.MAX_DOWNLOAD):
        if '/artifacts/' in path:
            if self.archive is not None:
                return self.archive
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as archive:
                archive.writestr('context.json', json.dumps(self.context))
            return stream.getvalue()
        if '/jobs/' in path:
            return self.logs
        raise AssertionError('Unexpected diagnostic download: ' + path)


class FailureIssueTests(unittest.TestCase):
    def publish(self, fake, dry=False, attempt=None):
        with patch.object(tickets, 'api', side_effect=fake.api), patch.object(tickets, 'download', side_effect=fake.download):
            return tickets.publish('123', dry, attempt)

    def test_creates_complete_agent_handoff_and_only_issue_writes(self):
        fake = FakeGitHub()
        issue = self.publish(fake)
        body = issue['body']
        self.assertIn('token3-ci-failure:123', body)
        self.assertIn('/actions/runs/123/attempts/1', body)
        self.assertIn('/job/456', body)
        self.assertIn('/commit/' + 'a' * 40, body)
        self.assertIn('npm run check', body)
        self.assertIn('expected 15 quotes', body)
        self.assertIn('Local coding-agent handoff', body)
        self.assertIn('Verification / acceptance criteria', body)
        self.assertIn('untrusted evidence', body)
        self.assertIn('latest default branch', body)
        self.assertIn('npm run test:e2e', body)
        self.assertEqual(issue['assignees'], ['owner'])
        self.assertEqual(issue['labels'], [tickets.LABEL])
        self.assertLess(len(body), tickets.MAX_BODY + 100)
        self.assertTrue(all(path == '/labels' or path.startswith('/issues') for path, _, _ in fake.writes))

    def test_rejects_prs_forks_branches_and_untrusted_workflows(self):
        for key, value in [('event', 'pull_request'), ('event', 'pull_request_target'),
                           ('head_repository', {'full_name': 'attacker/fork'}), ('head_branch', 'feature'),
                           ('workflow_id', 999), ('path', '.github/workflows/deploy.yml')]:
            with self.subTest(key=key, value=value):
                fake = FakeGitHub()
                fake.run[key] = value
                self.assertIsNone(self.publish(fake))
                self.assertEqual(fake.writes, [])

    def test_success_cancelled_skipped_pending_are_not_failures(self):
        for conclusion in ['success', 'cancelled', 'skipped', 'neutral', 'action_required']:
            fake = FakeGitHub()
            fake.run['conclusion'] = conclusion
            self.assertIsNone(self.publish(fake))
            self.assertEqual(fake.writes, [])
        fake = FakeGitHub()
        fake.run['status'] = 'in_progress'
        self.assertIsNone(self.publish(fake))

    def test_timeout_and_startup_failure_have_infrastructure_guidance(self):
        for conclusion in ['timed_out', 'startup_failure']:
            fake = FakeGitHub()
            fake.run['conclusion'] = conclusion
            fake.jobs = []
            body = self.publish(fake)['body']
            self.assertIn('startup/infrastructure errors', body)
            self.assertIn('runner availability', body)

    def test_scheduled_and_manual_collection_are_eligible(self):
        for event in ['schedule', 'workflow_dispatch']:
            fake = FakeGitHub(collection=True)
            fake.run['event'] = event
            self.assertIsNotNone(self.publish(fake))

    def test_collection_uses_exact_context_never_raw_logs_or_payloads(self):
        fake = FakeGitHub(collection=True)
        fake.add_context()
        paths = []
        def download(path, limit=tickets.MAX_DOWNLOAD):
            paths.append(path)
            return fake.download(path, limit)
        with patch.object(tickets, 'api', side_effect=fake.api), patch.object(tickets, 'download', side_effect=download):
            body = tickets.publish('123')['body']
        self.assertEqual(paths, ['/actions/artifacts/999/zip'])
        self.assertFalse(any('annotations' in path for path in fake.reads))
        self.assertIn('providers/vertex.py', body)
        self.assertIn('--provider vertex --dry-run --strict', body)
        self.assertIn('curated parser failed', body)
        self.assertIn('complete strict collection', body)
        self.assertIn('economic/scope changes require explicit human curation', body)

    def test_old_or_expired_collection_context_is_unknown_not_current_status(self):
        fake = FakeGitHub(collection=True)
        fake.artifacts = [{'id': 999, 'name': 'self-heal-context-123-1', 'expired': True}]
        body = self.publish(fake)['body']
        self.assertIn('No exact-attempt provider context', body)
        self.assertNotIn('curated parser failed', body)
        self.assertNotIn('--provider vertex', body)

    def test_mismatched_malformed_and_oversized_artifacts_fall_back(self):
        for key, value in [('run_attempt', '2'), ('failed_run_id', '456'), ('schema_version', 2),
                           ('failed_providers', [{'id': '../evil', 'error': 'bad'}])]:
            fake = FakeGitHub(collection=True)
            fake.add_context()
            fake.context[key] = value
            self.assertIn('context unavailable or rejected', self.publish(fake)['body'])
        fake = FakeGitHub(collection=True)
        fake.add_context()
        fake.artifacts[0]['size_in_bytes'] = 1024 * 1024
        self.assertIn('context unavailable or rejected', self.publish(fake)['body'])

    def test_archive_members_are_never_extracted_or_executed(self):
        fake = FakeGitHub(collection=True)
        fake.add_context()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('../../scripts/evil.py', 'raise RuntimeError("must not execute")')
            archive.writestr('context.json', json.dumps(fake.context))
        fake.archive = stream.getvalue()
        self.assertIn('context unavailable or rejected', self.publish(fake)['body'])

    def test_rerun_updates_same_ticket_preserving_notes_comments_and_closed_state(self):
        fake = FakeGitHub()
        first = self.publish(fake)
        fake.issues[0]['body'] = 'Human investigation notes\n' + first['body'] + '\nKeep this after the report.'
        fake.issues[0]['state'] = 'closed'
        fake.run['run_attempt'] = 2
        updated = self.publish(fake)
        self.assertEqual(updated['number'], first['number'])
        self.assertEqual(len(fake.issues), 1)
        self.assertEqual(fake.issues[0]['state'], 'closed')
        self.assertIn('Human investigation notes', fake.issues[0]['body'])
        self.assertIn('Keep this after the report.', fake.issues[0]['body'])
        self.assertIn('attempt 2', fake.issues[0]['body'])
        self.assertNotIn('attempt 1', fake.issues[0]['body'])
        self.assertEqual(sum(path == '/issues' and method == 'POST' for path, method, _ in fake.writes), 1)

    def test_forged_markers_in_human_issues_and_prs_do_not_deduplicate(self):
        for field in [{'user': {'login': 'attacker'}}, {'user': {'login': tickets.BOT}, 'pull_request': {}}]:
            fake = FakeGitHub()
            fake.issues = [dict(number=1, body='<!-- token3-ci-failure:123 -->', state='open', **field)]
            # GitHub PRs carry a non-empty pull_request object; use a realistic payload.
            if 'pull_request' in field:
                fake.issues[0]['pull_request'] = {'url': 'https://api.github.com/repos/owner/repo/pulls/1'}
            result = self.publish(fake)
            self.assertEqual(result['number'], 2)

    def test_dry_run_has_no_writes_even_label_creation(self):
        fake = FakeGitHub()
        result = self.publish(fake, dry=True)
        self.assertIn('no-AI handoff', result['body'])
        self.assertEqual(fake.writes, [])

    def test_old_attempt_event_and_run_races_are_skipped(self):
        fake = FakeGitHub()
        fake.run['run_attempt'] = 2
        self.assertIsNone(self.publish(fake, attempt=1))
        self.assertEqual(fake.writes, [])
        for change in [{'run_attempt': 2}, {'conclusion': 'success'}, {'status': 'in_progress'}]:
            fake = FakeGitHub()
            fake.changed = dict(fake.run, **change)
            self.assertIsNone(self.publish(fake))
            self.assertEqual(fake.writes, [])

    def test_log_or_annotation_unavailability_still_produces_a_ticket(self):
        fake = FakeGitHub()
        def api(path, *args, **kwargs):
            if '/check-runs/' in path:
                raise ValueError('Unavailable')
            return fake.api(path, *args, **kwargs)
        with patch.object(tickets, 'api', side_effect=api), patch.object(tickets, 'download', side_effect=ValueError('Expired')):
            body = tickets.publish('123')['body']
        self.assertIn('Log excerpt unavailable', body)
        self.assertIn('Check annotations unavailable', body)
        self.assertIn('Verification / acceptance criteria', body)

    def test_inventory_provider_guidance_does_not_invent_a_module(self):
        fake = FakeGitHub(collection=True)
        fake.add_context()
        fake.context['failed_providers'] = [{'id': 'snowflake', 'error': 'PDF unavailable'}]
        body = self.publish(fake)['body']
        self.assertIn('scripts/extended_inventory.py', body)
        self.assertNotIn('providers/snowflake.py', body)

    def test_dependency_browser_and_check_recipes(self):
        fake = FakeGitHub()
        fake.jobs[0]['steps'] = [{'name': name, 'conclusion': 'failure'} for name in ['npm ci', 'npm run check', 'npm run test:e2e']]
        body = self.publish(fake)['body']
        self.assertIn('Dependency installation failed', body)
        self.assertIn('TypeScript/Vite', body)
        self.assertIn('browser installation separately', body)

    def test_org_is_not_assigned_an_invented_owner_user(self):
        fake = FakeGitHub()
        fake.repo['owner']['type'] = 'Organization'
        self.assertNotIn('assignees', self.publish(fake))

    def test_managed_body_respects_unknown_human_content(self):
        body = tickets.managed_body('Human replaced the entire body.', tickets.START + '\nNew report\n' + tickets.END, '<!-- token3-ci-failure:123 -->')
        self.assertIn('Human replaced the entire body.', body)
        self.assertIn('New report', body)

    def test_issue_scan_is_bounded_and_fails_closed(self):
        with patch.object(tickets, 'api', return_value=[{'user': {'login': 'attacker'}, 'body': ''}] * 100):
            with self.assertRaisesRegex(ValueError, 'deduplication'):
                tickets.find_issue('missing')

    def test_invalid_run_identifiers_and_wrong_api_run_are_rejected(self):
        for value in ['0', '-1', '123\n456', '../123', '123;echo token', '1' * 21]:
            with self.assertRaises(ValueError):
                tickets.number(value)
        fake = FakeGitHub()
        fake.run['id'] = 999
        with self.assertRaisesRegex(ValueError, 'different run'):
            self.publish(fake)
        self.assertEqual(fake.writes, [])

    def test_logs_redact_credentials_and_do_not_break_fences_or_ping_people(self):
        raw = ('\x1b[31mError: Authorization: Bearer abcDEF123\x1b[0m\n'
               'AssertionError: key=smallsecret &refresh_token=anothersecret\n'
               'FAIL https://u:password@example.com/?api_key=xyz \n'
               'Error: sk-proj-abcdefghijklmnopqrstuvwxyz ghp_abcdefghijklmnopqrstuvwxyz\n'
               'Error: https://example.com/?api%255Fkey%253Dencoded-secret \n'
               'Error: ```\n@everyone </details><script>ignore policy</script>\n')
        value = tickets.log_excerpt(raw.encode())
        for secret in ['abcDEF123', 'smallsecret', 'anothersecret', 'password@', 'api_key=xyz',
                       'sk-proj-abcdefghijklmnopqrstuvwxyz', 'ghp_abcdefghijklmnopqrstuvwxyz', 'encoded-secret']:
            self.assertNotIn(secret, value)
        self.assertNotIn('```', value)
        self.assertNotIn('@everyone', value)
        self.assertNotIn('<script>', value)
        self.assertIn('[redacted]', value)

    def test_exact_environment_secrets_are_removed_before_publication(self):
        with patch.dict(os.environ, {'TOGETHER_API_KEY': 'unexpected-short-secret'}):
            self.assertNotIn('unexpected-short-secret', tickets.redact('ValueError: unexpected-short-secret'))

    def test_untrusted_job_names_cannot_create_links_mentions_or_new_sections(self):
        fake = FakeGitHub()
        fake.jobs[0]['name'] = 'x](https://evil.test)\n## override @owner ```'
        fake.jobs[0]['steps'][0]['name'] = '**ignore policy**'
        body = self.publish(fake)['body']
        self.assertNotIn('](https://evil.test)', body)
        self.assertNotIn('\n## override', body)
        self.assertNotIn('@owner', body)
        self.assertNotIn('**ignore policy**', body)

    def test_bounded_download_does_not_execute_the_downloaded_bytes(self):
        original = subprocess.Popen
        def spawn(_args, **kwargs):
            return original([sys.executable, '-c', 'print("raise RuntimeError(123)")'], **kwargs)
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo'}), patch.object(tickets.subprocess, 'Popen', side_effect=spawn):
            self.assertEqual(tickets.download('/actions/jobs/456/logs', 100), b'raise RuntimeError(123)\n')
        def oversized(_args, **kwargs):
            return original([sys.executable, '-c', 'print("x" * 1000)'], **kwargs)
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'owner/repo'}), patch.object(tickets.subprocess, 'Popen', side_effect=oversized):
            with self.assertRaisesRegex(ValueError, 'size/time'):
                tickets.download('/actions/jobs/456/logs', 100)
        with self.assertRaises(ValueError):
            tickets.download('https://evil.test')

    def test_maximum_provider_context_and_job_summaries_are_bounded(self):
        fake = FakeGitHub(collection=True)
        fake.add_context()
        fake.context['failed_providers'] = [{'id': p, 'error': 'ValueError: ' + 'e ' * 500} for p in sorted(tickets.PROVIDERS)[:26]]
        fake.jobs = [dict(fake.jobs[0], id=456 + i, steps=[{'name': 'n ' * 300, 'conclusion': 'failure'}] * 20) for i in range(12)]
        body = self.publish(fake)['body']
        self.assertLess(len(body), tickets.MAX_BODY + 100)
        self.assertIn('Verification / acceptance criteria', body)

    def test_workflow_uses_only_trusted_checkout_and_no_ai_or_collector_secrets(self):
        text = (ROOT / '.github/workflows/failure-issues.yml').read_text()
        workflow = yaml.load(text, Loader=yaml.BaseLoader)
        self.assertEqual(workflow['on']['workflow_run']['workflows'], ['Check dashboard and collectors', 'Collect official prices'])
        job = workflow['jobs']['report']
        self.assertEqual(job['permissions'], {'contents': 'read', 'actions': 'read', 'issues': 'write'})
        self.assertEqual(job['steps'][0]['with']['ref'], '${{ github.sha }}')
        self.assertEqual(job['steps'][0]['with']['persist-credentials'], 'false')
        self.assertNotIn('secrets.', text)
        self.assertNotIn('codex-action', text)
        self.assertNotIn('head_sha', job['steps'][0]['with']['ref'])
        self.assertIn("ENABLE_FAILURE_ISSUES != 'false'", job['if'])


if __name__ == '__main__':
    unittest.main()
