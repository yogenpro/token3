import base64
import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml
from scripts import self_heal as heal
from scripts.self_heal_policy import (
    commit_sha, digest, identifier, last_good_quotes, review_approved,
    semantic_quotes, validate_parser, validate_proposal,
)

ROOT = Path(__file__).resolve().parent.parent
SHA = 'a' * 40
BASE = 'b' * 40
BEFORE = '''from .common import observation, require_models, snapshot
SOURCE = "https://example.com/pricing"
def collect(aliases):
    return None

def parse(body, aliases):
    records = []
    require_models(records, [], aliases)
    return snapshot(records, body, SOURCE)
'''
AFTER = BEFORE.replace('    records = []', '    lines = body.splitlines()\n    records = []')
TEST = 'import unittest\nclass Regression(unittest.TestCase):\n    def test_layout(self):\n        self.assertEqual(1, 1)\n'


def proposal():
    return {'summary': 'Read the changed layout without reinterpreting pricing.', 'files': [
        {'path': 'providers/vertex.py', 'content': AFTER},
        {'path': 'tests/test_recovery_123.py', 'content': TEST}]}


def evidence():
    return {'failed_run_id': '123', 'base_sha': BASE, 'base_parser': BEFORE, 'provider': 'vertex',
            'default_branch': 'main', 'issue': 4, 'mode': 'repair'}


class RecoveryPolicyTests(unittest.TestCase):
    def test_identifiers_cannot_be_shell_or_path_inputs(self):
        for value in ('', '0', '../1', '1\nfoo=bar', '$(id)', '123; echo x'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                identifier(value)
        for value in ('main', SHA + '\n', '$(id)', 'a' * 39):
            with self.subTest(value=value), self.assertRaises(ValueError):
                commit_sha(value)
        self.assertEqual(identifier('123'), '123')
        self.assertEqual(commit_sha(SHA), SHA)

    def test_small_pure_parser_change_and_additive_regression_are_allowed(self):
        self.assertEqual(set(validate_proposal(proposal(), evidence())), {'providers/vertex.py', 'tests/test_recovery_123.py'})
        changed = AFTER.replace('from .common', 'import re\nfrom .common') + '\ndef _recovery_header(cell):\n    return cell.split()\n'
        validate_parser(BEFORE, changed)

    def test_transport_constants_existing_helpers_and_checks_are_immutable(self):
        for changed in [AFTER.replace('return None', 'return []'),
                        AFTER.replace('https://example.com/pricing', 'https://attacker.invalid'),
                        AFTER.replace('    require_models(records, [], aliases)\n', ''),
                        AFTER.replace('snapshot(records, body, SOURCE)', 'snapshot(records, body, SOURCE, True)'),
                        AFTER.replace('def parse(body, aliases)', 'def parse(body)'),
                        AFTER.replace('from .common import', 'from .other import')]:
            with self.subTest(source=changed), self.assertRaises(ValueError):
                validate_parser(BEFORE, changed)

    def test_reflection_environment_network_global_mutation_and_import_side_effects_are_rejected(self):
        for statement in ["os.environ['KEY']", "fetch_text(SOURCE)", "observation.__globals__", "globals()",
                          "body.write_text('x')", "SOURCE = 'elsewhere'", "getattr(observation, 'name')",
                          "global SOURCE", "import os", "collect(aliases)", "re.enum.sys._getframe().f_locals", "body._private"]:
            changed = AFTER.replace('    records = []', '    ' + statement + '\n    records = []')
            with self.subTest(statement=statement), self.assertRaises(ValueError):
                validate_parser(BEFORE, changed)
        for suffix in ['\ndef helper():\n    return 1\n', '\n@collect\ndef _recovery_helper():\n    return 1\n',
                       '\ndef _recovery_helper(x=collect()):\n    return x\n',
                       '\ndef _recovery_helper(x: collect()):\n    return x\n',
                       '\ndef collect(x=collect()):\n    return 1\n' + BEFORE[BEFORE.index('def collect'):]]:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                validate_parser(BEFORE, AFTER + suffix)
        with self.assertRaises(ValueError):
            validate_parser(BEFORE, 'import json as snapshot\n' + AFTER)

    def test_no_data_workflow_dependencies_existing_tests_or_path_tricks(self):
        for path in ('data/latest_prices.json', '.github/workflows/collect.yml', 'requirements.txt',
                     'providers/common.py', 'tests/test_public_pricing.py', 'tests/fixtures/vertex.html',
                     '../providers/vertex.py', '/providers/vertex.py', 'tests//test_recovery_123.py'):
            candidate = proposal(); candidate['files'].append({'path': path, 'content': 'x'})
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_proposal(candidate, evidence())

    def test_proposals_require_bounded_unique_files_and_real_test_methods(self):
        for modify in [lambda p: p['files'].pop(),
                       lambda p: p['files'].append(p['files'][0]),
                       lambda p: p['files'][0].update(content='x' * (128 * 1024 + 1)),
                       lambda p: p['files'][0].update(content=BEFORE),
                       lambda p: p['files'][1].update(content='import unittest\n'),
                       lambda p: p.update(command='echo injected')]:
            candidate = proposal(); modify(candidate)
            with self.assertRaises((ValueError, SyntaxError)):
                validate_proposal(candidate, evidence())

    def test_regressions_cannot_write_files_import_transport_or_monkeypatch_tests(self):
        for code in ["from pathlib import Path\nPath('data/status.json').write_text('x')\n",
                     'import os\n', 'from unittest.mock import patch\n', 'from providers import common\n',
                     'unittest.TestCase.assertEqual = lambda *args: None\n']:
            candidate = proposal(); candidate['files'][1]['content'] += code
            with self.subTest(code=code), self.assertRaises(ValueError):
                validate_proposal(candidate, evidence())

    def test_review_is_strict_and_bound_to_the_exact_tested_commit(self):
        candidate = {'head_sha': SHA, 'ci_run_id': '456'}
        review = {'approved': True, **candidate, 'reason': 'Supported cells, credible regression, no unresolved risks.', 'risks': []}
        self.assertTrue(review_approved(review, candidate))
        for change in [dict(approved=False), dict(approved='true'), dict(head_sha=BASE), dict(ci_run_id='999'),
                       dict(risks=['Unverified unit']), dict(reason=''), dict(shell='echo yes')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                review_approved(dict(review, **change), candidate)

    def test_economic_scope_and_provenance_changes_do_not_match_last_good(self):
        row = {'provider_model_id': 'm', 'input_per_million': 1, 'currency': 'USD', 'region': 'global',
               'source_url': 'https://example.com', 'min_input_tokens': 0, 'max_input_tokens': 200000}
        for change in [dict(input_per_million=0), dict(currency=None), dict(region='regional'),
                       dict(max_input_tokens=100000), dict(provider_model_id='m-new'), dict(source_url='https://attacker.invalid')]:
            self.assertNotEqual(semantic_quotes([row]), semantic_quotes([dict(row, **change)]))
        with self.assertRaises(ValueError):
            last_good_quotes('vertex', [], [])


class RecoveryOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GITHUB_REPOSITORY': 'yogenpro/token3', 'GITHUB_RUN_ID': '789'}, clear=True)
        self.env.start(); self.addCleanup(self.env.stop)

    def test_failed_context_is_small_redacted_and_excludes_stale_errors(self):
        status = {'last_run_at': '2026-10-08T13:29:47Z', 'providers': [
            {'id': 'vertex', 'state': 'error', 'last_attempt_at': '2026-10-08T13:29:47Z', 'error': 'Problem with SECRET', 'source_payload': 'private'},
            {'id': 'old', 'state': 'error', 'last_attempt_at': '2026-10-07T13:29:47Z', 'error': 'old'},
            {'id': 'ok', 'state': 'ok', 'last_attempt_at': '2026-10-08T13:29:47Z'}]}
        with patch.dict(os.environ, {'FIREWORKS_API_KEY': 'SECRET'}):
            value = heal.context_from_status(status, '123', '1')
        self.assertEqual(value['failed_providers'], [{'id': 'vertex', 'error': 'Problem with [redacted]', 'last_attempt_at': status['last_run_at']}])
        self.assertNotIn('private', json.dumps(value))

    def test_fork_manual_replacement_wrong_workflow_and_old_run_cannot_trigger_repair(self):
        run = {'workflow_id': 9, 'head_repository': {'full_name': 'yogenpro/token3'}, 'head_branch': 'main',
               'event': 'schedule', 'status': 'completed', 'conclusion': 'failure', 'created_at': '2026-10-08T13:29:37Z'}
        now = datetime(2026, 10, 8, 16, tzinfo=timezone.utc)
        heal.validate_failed_run(run, 'yogenpro/token3', 9, 'main', now)
        for change in [dict(head_repository={'full_name': 'attacker/token3'}), dict(event='workflow_dispatch'),
                       dict(event='pull_request'), dict(head_branch='self-heal/test'), dict(workflow_id=10),
                       dict(conclusion='success'), dict(created_at='2026-09-01T13:29:37Z')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                heal.validate_failed_run(dict(run, **change), 'yogenpro/token3', 9, 'main', now)

    def test_ci_must_be_original_bot_dispatch_on_the_exact_recovery_sha(self):
        candidate = {'head_sha': SHA, 'branch': 'self-heal/collection-123'}
        run = {'workflow_id': 8, 'head_repository': {'full_name': 'yogenpro/token3'}, 'event': 'workflow_dispatch',
               'head_sha': SHA, 'head_branch': candidate['branch'], 'actor': {'login': heal.BOT}, 'run_attempt': 1,
               'display_title': 'Recovery CI 123 / ' + SHA, 'status': 'completed', 'conclusion': 'success'}
        heal.ci_run_valid(run, candidate, evidence(), 8)
        for change in [dict(event='pull_request'), dict(head_sha=BASE), dict(actor={'login': 'attacker'}),
                       dict(head_repository={'full_name': 'attacker/token3'}), dict(run_attempt=2),
                       dict(display_title='Unrelated success'), dict(conclusion='failure')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                heal.ci_run_valid(dict(run, **change), candidate, evidence(), 8)

    def test_rejected_or_missing_review_never_reaches_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory); e = evidence(); candidate = {'head_sha': SHA, 'ci_run_id': '456'}
            for name, value in [('evidence', e), ('proposal', proposal()), ('candidate', candidate),
                                ('review', {'approved': False, **candidate, 'reason': 'Unsafe code', 'risks': ['Unsafe code']})]:
                heal.save(directory / (name + '.json'), value)
            with patch.object(heal, 'api') as api, self.assertRaises(ValueError):
                heal.finish(SimpleNamespace(directory=directory))
            api.assert_not_called()
            (directory / 'review.json').unlink()
            with patch.object(heal, 'api') as api, self.assertRaises(ValueError):
                heal.finish(SimpleNamespace(directory=directory))
            api.assert_not_called()

    def test_replacement_dispatch_is_single_and_failure_does_not_close_issue(self):
        e = evidence()
        with patch.object(heal, 'comment'), patch.object(heal, 'dispatch_and_wait', return_value={'html_url': 'https://github.com/run', 'conclusion': 'failure'}) as dispatch, \
                patch.object(heal, 'api') as api, self.assertRaises(ValueError):
            heal.makeup(e, SHA)
        dispatch.assert_called_once()
        self.assertEqual(dispatch.call_args.args[:3], ('collect.yml', 'main', {'recovery_origin_run_id': '123'}))
        api.assert_not_called()

    def test_verified_merge_supplies_expected_sha_and_then_dispatches_makeup(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory); candidate = {'head_sha': SHA, 'ci_run_id': '456', 'pr': 5}
            for name, value in [('evidence', evidence()), ('proposal', proposal()), ('candidate', candidate),
                                ('review', {'approved': True, 'head_sha': SHA, 'ci_run_id': '456', 'reason': 'Safe layout fix.', 'risks': []})]:
                heal.save(directory / (name + '.json'), value)
            with patch.object(heal, 'verify_candidate', return_value='c' * 40) as verify, patch.object(heal, 'comment'), \
                    patch.object(heal, 'merge_verified', return_value=BASE) as merge, \
                    patch.object(heal, 'makeup') as makeup, patch.object(heal, 'api'):
                heal.finish(SimpleNamespace(directory=directory))
            verify.assert_called_once()
            merge.assert_called_once_with(candidate, evidence(), 'c' * 40)
            makeup.assert_called_once_with(evidence(), BASE)

    def test_pr_blobs_tree_modes_head_base_and_ci_are_revalidated_before_writes(self):
        p, e = proposal(), evidence()
        contents = validate_proposal(p, e)
        candidate = {'head_sha': SHA, 'base_sha': BASE, 'branch': 'self-heal/collection-123', 'pr': 5,
                     'ci_run_id': '456', 'proposal_sha256': digest(contents)}
        paths = list(contents)
        pr = {'state': 'open', 'draft': False, 'user': {'login': heal.BOT},
              'head': {'repo': {'full_name': 'yogenpro/token3'}, 'ref': candidate['branch'], 'sha': SHA}, 'base': {'ref': 'main'}}
        ci = {'workflow_id': 8, 'head_repository': {'full_name': 'yogenpro/token3'}, 'event': 'workflow_dispatch',
              'head_sha': SHA, 'head_branch': candidate['branch'], 'actor': {'login': heal.BOT}, 'run_attempt': 1,
              'display_title': 'Recovery CI 123 / ' + SHA, 'status': 'completed', 'conclusion': 'success'}
        responses = {'/branches/main': {'protected': False}, '/pulls/5': pr, '/git/ref/heads/main': {'object': {'sha': BASE}},
            '/git/ref/heads/' + candidate['branch']: {'object': {'sha': SHA}},
            '/compare/{}...{}'.format(BASE, SHA): {'total_commits': 1, 'files': [
                {'filename': path, 'status': 'modified' if i == 0 else 'added', 'sha': str(i) * 40} for i, path in enumerate(paths)]},
            '/git/trees/{}?recursive=1'.format(SHA): {'sha': 'c' * 40, 'truncated': False, 'tree': [
                {'path': path, 'mode': '100644', 'type': 'blob'} for path in paths]},
            '/actions/runs/456': ci, '/actions/workflows/ci.yml': {'id': 8},
            '/actions/runs/456/jobs': {'jobs': [{'name': 'check', 'conclusion': 'success'}]}}
        for i, path in enumerate(paths):
            responses['/git/blobs/' + str(i) * 40] = {'size': len(contents[path]), 'encoding': 'base64',
                                                   'content': base64.b64encode(contents[path].encode()).decode()}
        with patch.object(heal, 'api', side_effect=lambda path: responses[path]) as api:
            self.assertEqual(heal.verify_candidate(candidate, p, e), 'c' * 40)
            self.assertTrue(all(len(c.args) == 1 for c in api.call_args_list))
        changes = [('/branches/main', lambda v: v.update(protected=True)),
                   ('/pulls/5', lambda v: v['head'].update(sha=BASE)),
                   ('/pulls/5', lambda v: v['user'].update(login='attacker')),
                   ('/git/ref/heads/main', lambda v: v['object'].update(sha=SHA)),
                   ('/git/trees/{}?recursive=1'.format(SHA), lambda v: v['tree'][0].update(mode='120000')),
                   ('/git/blobs/' + '0' * 40, lambda v: v.update(content=base64.b64encode(b'changed').decode())),
                   ('/actions/runs/456', lambda v: v.update(conclusion='failure'))]
        for path, mutate in changes:
            changed = copy.deepcopy(responses); mutate(changed[path])
            with self.subTest(path=path), patch.object(heal, 'api', side_effect=lambda path: changed[path]) as api, self.assertRaises(ValueError):
                heal.verify_candidate(candidate, p, e)
            self.assertTrue(all(len(c.args) == 1 for c in api.call_args_list))

    def test_merge_uses_tested_tree_two_parents_and_atomic_nonforced_ref_update(self):
        candidate = {'pr': 5, 'head_sha': SHA}
        with patch.object(heal, 'branch_sha', return_value=BASE), patch.object(heal, 'api', side_effect=[
                {'sha': 'd' * 40}, {'state': 'open', 'head': {'sha': SHA}}, {'protected': False}, {}, {'merged': True, 'head': {'sha': SHA}}]) as api:
            result = heal.merge_verified(candidate, evidence(), 'c' * 40)
        self.assertEqual(result, 'd' * 40)
        self.assertEqual(api.call_args_list[0].args[2]['tree'], 'c' * 40)
        self.assertEqual(api.call_args_list[0].args[2]['parents'], [BASE, SHA])
        self.assertEqual(api.call_args_list[3].args, ('/git/refs/heads/main', 'PATCH', {'sha': 'd' * 40, 'force': False}))
        with patch.object(heal, 'branch_sha', return_value=SHA), patch.object(heal, 'api', side_effect=[
                {'sha': 'd' * 40}, {'state': 'open', 'head': {'sha': SHA}}]) as api, self.assertRaises(ValueError):
            heal.merge_verified(candidate, evidence(), 'c' * 40)
        self.assertEqual(len(api.call_args_list), 2)

    def test_ordinary_ci_cannot_skip_recovery_origin_and_sha_binding(self):
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'pull_request', 'RECOVERY_HEAD_SHA': SHA}), \
                patch.object(heal, 'api') as api, self.assertRaises(ValueError):
            heal.ci_context(SimpleNamespace(directory=Path('.')))
        api.assert_not_called()
        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'workflow_dispatch', 'RECOVERY_HEAD_SHA': SHA, 'GITHUB_SHA': BASE}), \
                patch.object(heal, 'api') as api, self.assertRaises(ValueError):
            heal.ci_context(SimpleNamespace(directory=Path('.')))
        api.assert_not_called()

    def test_real_vertex_layout_replay_and_original_parser_regression(self):
        from providers import vertex
        from scripts.normalize import catalog
        from datetime import date
        _, aliases = catalog()
        legacy = (ROOT / 'tests/fixtures/vertex.html').read_text()
        before, _, claude = legacy.partition('<button id="tab-61"')
        _, regional_tab, regional = claude.partition('<button id="tab-94"')
        body = before + (ROOT / 'tests/fixtures/vertex-claude-mixed-bands.html').read_text() + regional_tab + regional
        parsed = vertex.parse(body, aliases, date(2026, 10, 8))
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for name in ('providers', 'scripts', 'catalog', 'tests'):
                shutil.copytree(ROOT / name, directory / name, ignore=shutil.ignore_patterns('__pycache__'))
            test = directory / 'tests/test_recovery_123.py'
            test.write_text('import unittest\nfrom pathlib import Path\nfrom providers import vertex\nfrom scripts.normalize import catalog\n'
                            'class Regression(unittest.TestCase):\n    def test_mixed_columns(self):\n'
                            '        _, aliases = catalog()\n'
                            '        body = (Path(__file__).parent / "fixtures/recovery-123-layout.html").read_text()\n'
                            '        self.assertEqual(len(vertex.parse(body, aliases).records), 15)\n')
            (directory / 'tests/fixtures/recovery-123-layout.html').write_text(body)
            e = evidence(); e.update(provider='vertex', source_payload=body, source_url=vertex.SOURCE,
                source_sha256=hashlib.sha256(body.encode()).hexdigest(), observed_at='2026-10-08T16:54:00Z',
                authoritative_catalog=False,
                expected=heal.normalized_quotes('vertex', parsed.records, '2026-10-08T16:54:00Z', parsed.source_sha256),
                base_parser=(ROOT / 'providers/vertex.py').read_text().replace('claude = claude_token_table(header)',
                    'claude = len(header) == 4 and header[:2] == ["Model", "Type"] and "200K" in header[2]'))
            heal.save(directory / '.recovery/evidence.json', e)
            with patch.object(heal, 'ROOT', directory):
                heal.probe(SimpleNamespace(directory=directory / '.recovery'))
                e['expected'][0]['input_per_million'] = 999
                heal.save(directory / '.recovery/evidence.json', e)
                with self.assertRaisesRegex(ValueError, 'Replay changed reviewed'):
                    heal.probe(SimpleNamespace(directory=directory / '.recovery'))


class RecoveryWorkflowTests(unittest.TestCase):
    def test_agents_are_read_only_separate_from_github_writers_and_pinned(self):
        workflow = yaml.load((ROOT / '.github/workflows/self-heal.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertNotIn('pull_request_target', workflow['on'])
        self.assertNotIn('pull_request', workflow['on'])
        self.assertIn("vars.ENABLE_SELF_HEALING == 'true'", workflow['jobs']['prepare']['if'])
        self.assertIn("event == 'schedule'", workflow['jobs']['prepare']['if'])
        self.assertIn('!cancelled()', workflow['jobs']['finalize']['if'])
        for job in ('repair', 'review'):
            self.assertTrue(all(v == 'read' for v in workflow['jobs'][job]['permissions'].values()))
            steps = workflow['jobs'][job]['steps']
            agent = next(s for s in steps if s.get('uses', '').startswith('openai/codex-action@'))
            self.assertEqual(agent['with']['sandbox'], 'read-only')
            self.assertEqual(agent['with']['safety-strategy'], 'drop-sudo')
            self.assertNotIn('*', agent['with'].get('allow-users', ''))
            self.assertNotIn('GH_TOKEN', json.dumps(steps))
        for job in workflow['jobs'].values():
            for step in job['steps']:
                if 'uses' in step:
                    self.assertRegex(step['uses'], r'@[a-f0-9]{40}$')
        self.assertNotIn('FIREWORKS_API_KEY', json.dumps(workflow))
        self.assertNotIn('GOOGLE_CLOUD_BILLING_API_KEY', json.dumps(workflow))

    def test_recovery_ci_is_secret_free_and_uses_explicit_dispatch_and_replay(self):
        workflow = yaml.load((ROOT / '.github/workflows/ci.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertIn('workflow_dispatch', workflow['on'])
        self.assertTrue(all(v == 'read' for v in workflow['permissions'].values()))
        self.assertNotIn('secrets.', json.dumps(workflow))
        self.assertIn('scripts.self_heal probe', json.dumps(workflow))
        self.assertIn('recovery_head_sha', workflow['run-name'])
        collector = yaml.load((ROOT / '.github/workflows/collect.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertIn('recovery_origin_run_id', collector['on']['workflow_dispatch']['inputs'])
        self.assertEqual(collector['on']['schedule'][0]['cron'], '17 6 * * *')


if __name__ == '__main__':
    unittest.main()
