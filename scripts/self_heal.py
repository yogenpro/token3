"""Trusted orchestration for bounded parser recovery. AI output is data, never shell."""
import argparse
import base64
import importlib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import subprocess
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from scripts.self_heal_policy import (
    PARSERS, commit_sha, digest, identifier, last_good_quotes, require,
    review_approved, semantic_quotes, validate_proposal,
)

ROOT = Path(__file__).resolve().parent.parent
BOT = 'github-actions[bot]'
REPAIR_MODELS = {'gpt-6-luna', 'gpt-6.1-sol'}
REVIEW_MODELS = {'gpt-6.1-sol'}
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024


def load(path):
    require(path.stat().st_size <= MAX_EVIDENCE_BYTES + 512 * 1024, 'Recovery file exceeds size limit')
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def output(**values):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            for key, value in values.items():
                require(re.fullmatch(r'[a-z_]+', key) and '\n' not in str(value) and '\r' not in str(value), 'Unsafe workflow output')
                stream.write('{}={}\n'.format(key, value))


def repository():
    value = os.environ['GITHUB_REPOSITORY']
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', value), 'Invalid repository')
    return value


def api(path, method='GET', body=None, binary=False):
    require((path == '' or path.startswith('/')) and '://' not in path and '..' not in path, 'Unsafe API path')
    args = ['gh', 'api', 'repos/' + repository() + path, '--method', method]
    data = None
    if body is not None:
        args += ['--input', '-']
        data = json.dumps(body).encode()
    result = subprocess.run(args, input=data, capture_output=True, timeout=90)
    # Do not echo request/response bodies or token-bearing diagnostics.
    require(result.returncode == 0, 'GitHub API request failed: {} {}'.format(method, path))
    return result.stdout if binary else json.loads(result.stdout) if result.stdout else None


def branch_sha(branch):
    require(re.fullmatch(r'[A-Za-z0-9_./-]+', branch) and '..' not in branch, 'Invalid branch')
    return commit_sha(api('/git/ref/heads/' + branch)['object']['sha'])


def comment(issue, body):
    identifier(str(issue), 'issue number')
    api('/issues/{}/comments'.format(issue), 'POST', {'body': body[:16000]})


def context_from_status(status, run_id, attempt):
    identifier(str(run_id)); identifier(str(attempt), 'run attempt')
    failed = []
    for row in status['providers']:
        if row['state'] == 'error' and row['last_attempt_at'] == status['last_run_at']:
            error = str(row.get('error') or '')[:500]
            for key in ('TOGETHER_API_KEY', 'FIREWORKS_API_KEY', 'GOOGLE_CLOUD_BILLING_API_KEY'):
                secret = os.environ.get(key)
                if secret:
                    error = error.replace(secret, '[redacted]')
            failed.append({'id': row['id'], 'error': error, 'last_attempt_at': row['last_attempt_at']})
    return {'schema_version': 1, 'failed_run_id': str(run_id), 'run_attempt': str(attempt),
            'last_run_at': status['last_run_at'], 'failed_providers': failed}


def collect_context(args):
    status = load(ROOT / 'data/status.json')
    save(args.directory / 'context.json', context_from_status(status, os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT']))


def validate_failed_run(run, repo, workflow_id, default_branch, now=None):
    require(run['workflow_id'] == workflow_id and run['head_repository']['full_name'] == repo, 'Untrusted triggering workflow/repository')
    require(run['head_branch'] == default_branch and run['event'] == 'schedule', 'Only failed default-branch daily schedules are eligible')
    require(run['status'] == 'completed' and run['conclusion'] == 'failure', 'Run is not a completed failure')
    created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
    age = ((now or datetime.now(timezone.utc)) - created).total_seconds()
    require(0 <= age <= 7 * 86400, 'Run is outside the seven-day recovery window')


def artifact_context(run_id, attempt):
    name = 'self-heal-context-{}-{}'.format(run_id, attempt)
    artifacts = api('/actions/runs/{}/artifacts?per_page=100'.format(run_id))['artifacts']
    found = [a for a in artifacts if a['name'] == name and not a['expired']]
    if not found:
        return None
    require(len(found) == 1, 'Ambiguous failure context artifact')
    content = api('/actions/artifacts/{}/zip'.format(found[0]['id']), binary=True)
    require(len(content) <= 128 * 1024, 'Oversized failure context archive')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        require(archive.namelist() == ['context.json'], 'Unexpected failure context archive members')
        require(archive.getinfo('context.json').file_size <= 64 * 1024, 'Oversized failure context')
        context = json.loads(archive.read('context.json'))
    require(context['schema_version'] == 1 and context['failed_run_id'] == run_id and context['run_attempt'] == attempt, 'Failure context does not match this attempt')
    require(isinstance(context['failed_providers'], list) and len(context['failed_providers']) <= 26, 'Invalid provider failures')
    return context


def normalized_quotes(provider, records, observed_at, source_sha):
    from scripts.normalize import catalog, normalize
    _, aliases = catalog()
    rows = []
    for record in records:
        offering, price = normalize(record, aliases, observed_at, source_sha)
        require(offering['provider'] == provider, 'Provider changed during recovery replay')
        rows.append(dict(offering, **price))
    return semantic_quotes(rows)


def prepare(args):
    event = load(Path(os.environ['GITHUB_EVENT_PATH']))
    run_id = identifier(str(event.get('workflow_run', {}).get('id') or event.get('inputs', {}).get('failed_run_id') or ''))
    run = api('/actions/runs/' + run_id)
    repo = repository()
    # Obtain the actual default branch; do not trust an event-provided branch label.
    repo_info = api('')
    default = repo_info['default_branch']
    workflow = api('/actions/workflows/collect.yml')
    validate_failed_run(run, repo, workflow['id'], default)
    base = branch_sha(default)
    # Check out the fresh trusted default tip chosen by the API, never a PR head.
    require(subprocess.run(['git', 'checkout', '--detach', base], cwd=ROOT, capture_output=True).returncode == 0, 'Default branch moved; retry manually')
    marker = '<!-- token3-recovery:{} -->'.format(run_id)
    for page in range(1, 11):
        issues = api('/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&page={}'.format(page))
        if any(marker in (i.get('body') or '') and i['user']['login'] == BOT for i in issues):
            output(mode='skip'); print('This failed run already has a recovery attempt.'); return
        if len(issues) < 100:
            break
    else:
        raise ValueError('Cannot prove recovery deduplication')
    issue_body = {'title': 'Collection recovery for daily run ' + run_id,
        'body': marker + '\nOne bounded recovery attempt for https://github.com/{}/actions/runs/{}.\n\nParser-only changes may merge after replay, regression tests, CI and independent review. Other cases require manual intervention.'.format(repo, run_id)}
    if repo_info['owner']['type'] == 'User':
        issue_body['assignees'] = [repo_info['owner']['login']]
    issue = api('/issues', 'POST', issue_body)
    output(issue=str(issue['number']), failed_run_id=run_id, base_sha=base)
    minimal = {'failed_run_id': run_id, 'base_sha': base, 'default_branch': default, 'issue': issue['number'], 'mode': 'manual',
               'reason': 'No trustworthy collector-failure context was produced (infrastructure failure or old workflow).'}
    save(args.directory / 'evidence.json', minimal)
    context = artifact_context(run_id, str(run['run_attempt']))
    if context is None:
        # Compatibility with runs predating context artifacts. Require fresh failed
        # status inside that run's time window, not an arbitrary older error.
        status = load(ROOT / 'data/status.json')
        context = context_from_status(status, run_id, str(run['run_attempt']))
        started, ended = run['created_at'], run['updated_at']
        if not started <= context['last_run_at'] <= ended:
            context = None
    if context is None or not context['failed_providers']:
        output(mode='manual'); return
    failed = context['failed_providers']
    minimal['failure_context'] = context
    if len(failed) != 1 or failed[0]['id'] not in PARSERS or 'curated parser failed' not in failed[0]['error']:
        minimal['reason'] = 'Not a single reviewed-provider parser-layout failure. Outages, credentials, inventory-only sources and shared infrastructure require human review.'
        save(args.directory / 'evidence.json', minimal); output(mode='manual'); return
    provider = failed[0]['id']
    require(all(not os.environ.get(k) for k in ('TOGETHER_API_KEY', 'FIREWORKS_API_KEY', 'GOOGLE_CLOUD_BILLING_API_KEY', 'OPENAI_API_KEY')), 'Collector/AI credentials must not be present during evidence capture')
    from scripts.collect import PROVIDERS
    from scripts.normalize import catalog
    _, aliases = catalog()
    expected = last_good_quotes(provider, load(ROOT / 'data/offerings.json'), load(ROOT / 'data/latest_prices.json'))
    try:
        result = PROVIDERS[provider].collect(aliases)
    except Exception:
        minimal['reason'] = 'The public source cannot currently be fetched. No transport/authentication repair is authorized.'
        save(args.directory / 'evidence.json', minimal); output(mode='manual'); return
    require(result.source_payload is not None and len(result.source_payload.encode()) <= MAX_EVIDENCE_BYTES, 'Missing/oversized public evidence')
    require(result.source_kind not in ('api+documentation',) and not result.inventory_only, 'Authenticated or inventory-only evidence is not eligible')
    for key in ('GH_TOKEN', 'GITHUB_TOKEN'):
        secret = os.environ.get(key)
        require(not secret or secret not in result.source_payload, 'Credential appeared in public evidence')
    minimal.update(provider=provider, expected=expected, source_payload=result.source_payload, source_url=result.source_url,
                   source_sha256=result.source_sha256, observed_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                   base_parser=(ROOT / PARSERS[provider]).read_text(),
                   authoritative_catalog=provider in ('deepinfra', 'novita'))
    if not result.parse_error:
        require(normalized_quotes(provider, result.records, minimal['observed_at'], result.source_sha256) == expected,
                'Source pricing/scope changed; human review required')
        minimal.update(mode='retry', reason='Current trusted parser succeeds with unchanged reviewed quotes. Retry collection without a code change.')
    else:
        repair_model = os.environ.get('SELF_HEAL_REPAIR_MODEL') or 'gpt-6-luna'
        review_model = os.environ.get('SELF_HEAL_REVIEW_MODEL') or 'gpt-6.1-sol'
        require(repair_model in REPAIR_MODELS and review_model in REVIEW_MODELS, 'Unapproved recovery model')
        minimal.update(mode='repair', reason='Public-source parser failure reproduced; reviewed rates and scope must remain unchanged.',
                       repair_model=repair_model, review_model=review_model)
        output(repair_model=repair_model, review_model=review_model)
    save(args.directory / 'evidence.json', minimal)
    output(mode=minimal['mode'])


def ci_run_valid(run, candidate, evidence, workflow_id):
    require(run['workflow_id'] == workflow_id and run['head_repository']['full_name'] == repository(), 'Untrusted CI workflow/repository')
    require(run['event'] == 'workflow_dispatch' and run['head_sha'] == candidate['head_sha'] and run['head_branch'] == candidate['branch'], 'CI is not bound to the proposed commit')
    require(run['actor']['login'] == BOT and run['run_attempt'] == 1, 'CI was not the original trusted dispatch')
    require(run['display_title'] == 'Recovery CI {} / {}'.format(evidence['failed_run_id'], candidate['head_sha']), 'CI lacks the recovery binding')
    require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Recovery CI did not pass')


def dispatch_and_wait(workflow, branch, inputs, sha, title=None, timeout=1200, notify_issue=None):
    before = {r['id'] for r in api('/actions/workflows/{}/runs?event=workflow_dispatch&per_page=100'.format(workflow))['workflow_runs']}
    api('/actions/workflows/{}/dispatches'.format(workflow), 'POST', {'ref': branch, 'inputs': inputs})
    deadline = time.monotonic() + timeout
    selected = None
    while time.monotonic() < deadline:
        if selected is None:
            runs = api('/actions/workflows/{}/runs?event=workflow_dispatch&per_page=100'.format(workflow))['workflow_runs']
            matches = [r for r in runs if r['id'] not in before and r['head_sha'] == sha and r['head_branch'] == branch
                       and r['actor']['login'] == BOT and (title is None or r['display_title'] == title)]
            require(len(matches) <= 1, 'Ambiguous dispatched run')
            selected = matches[0]['id'] if matches else None
            if selected is not None and notify_issue is not None:
                comment(notify_issue, 'Started {}: https://github.com/{}/actions/runs/{}.'.format(workflow, repository(), selected))
        if selected is not None:
            run = api('/actions/runs/' + str(selected))
            if run['status'] == 'completed':
                return run
        time.sleep(10)
    raise ValueError('Dispatched workflow did not finish within the recovery budget')


def publish(args):
    evidence = load(args.directory / 'evidence.json')
    proposal = load(args.directory / 'proposal.json')
    if proposal.get('files') == [] and isinstance(proposal.get('summary'), str):
        reason = json.dumps(proposal['summary'][:4000]).replace('`', '\\u0060')
        comment(evidence['issue'], 'The repair advisor declined to propose a safe patch:\n\n```json\n' + reason + '\n```')
        raise ValueError('No safe parser-only repair was proposed; human review required')
    contents = validate_proposal(proposal, evidence)
    require(branch_sha(evidence['default_branch']) == evidence['base_sha'], 'Default branch changed; automatic recovery stopped')
    for path in contents:
        if path != PARSERS[evidence['provider']]:
            require(not (ROOT / path).exists(), 'Regression files must be new; existing tests/fixtures cannot change')
    base_tree = api('/git/commits/' + evidence['base_sha'])['tree']['sha']
    tree = []
    for path, content in contents.items():
        blob = api('/git/blobs', 'POST', {'content': content, 'encoding': 'utf-8'})
        tree.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    new_tree = api('/git/trees', 'POST', {'base_tree': base_tree, 'tree': tree})
    commit = api('/git/commits', 'POST', {'message': 'fix: bounded parser recovery for daily run ' + evidence['failed_run_id'],
                                       'tree': new_tree['sha'], 'parents': [evidence['base_sha']]})
    head = commit_sha(commit['sha'])
    branch = 'self-heal/collection-' + evidence['failed_run_id']
    api('/git/refs', 'POST', {'ref': 'refs/heads/' + branch, 'sha': head})
    pr = api('/pulls', 'POST', {'title': 'Fix {} parser after daily collection failure'.format(evidence['provider']),
        'head': branch, 'base': evidence['default_branch'],
        'body': '<!-- token3-recovery:{} -->\nRecovery for #{}.\n\n{}\n\nNo data, history, workflow, source registry, transport or core-validation changes are allowed. Existing tests/fixtures are immutable. Auto-merge requires secret-free replay, a failing-before/passing-after regression, complete CI and an independent read-only AI review of this exact commit.'.format(evidence['failed_run_id'], evidence['issue'], proposal['summary'])})
    candidate = {'head_sha': head, 'base_sha': evidence['base_sha'], 'branch': branch, 'pr': pr['number'],
                 'proposal_sha256': digest(contents), 'ci_run_id': ''}
    save(args.directory / 'candidate.json', candidate)
    output(pr=str(pr['number']), head_sha=head)
    comment(evidence['issue'], 'Repair PR opened: {}. Explicit recovery CI is being dispatched; ordinary bot-created PR workflows may require manual approval.'.format(pr['html_url']))
    title = 'Recovery CI {} / {}'.format(evidence['failed_run_id'], head)
    run = dispatch_and_wait('ci.yml', branch, {'recovery_head_sha': head, 'recovery_origin_run_id': evidence['failed_run_id'],
        'recovery_workflow_run_id': os.environ['GITHUB_RUN_ID']}, head, title, timeout=1200, notify_issue=evidence['issue'])
    candidate['ci_run_id'] = str(run['id'])
    save(args.directory / 'candidate.json', candidate)
    ci_run_valid(run, candidate, evidence, api('/actions/workflows/ci.yml')['id'])
    jobs = api('/actions/runs/{}/jobs'.format(run['id']))['jobs']
    require(len(jobs) == 1 and jobs[0]['name'] == 'check' and jobs[0]['conclusion'] == 'success', 'Required CI job is missing/failed')
    output(ci_ok='true')


def ci_context(args):
    require(os.environ['GITHUB_EVENT_NAME'] == 'workflow_dispatch', 'Recovery CI requires an explicit dispatch')
    head = commit_sha(os.environ['RECOVERY_HEAD_SHA'])
    require(head == os.environ['GITHUB_SHA'], 'Recovery branch moved before CI started')
    checked = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, timeout=30)
    require(checked.returncode == 0 and checked.stdout.strip() == head, 'Recovery checkout is not the expected SHA')
    require(subprocess.run(['git', 'diff', '--quiet', 'HEAD'], cwd=ROOT, timeout=30).returncode == 0, 'Recovery checkout has tracked modifications')
    identifier(os.environ['RECOVERY_ORIGIN_RUN_ID'])
    source_id = identifier(os.environ['RECOVERY_WORKFLOW_RUN_ID'])
    source = api('/actions/runs/' + source_id)
    require(source['workflow_id'] == api('/actions/workflows/self-heal.yml')['id']
            and source['head_repository']['full_name'] == repository()
            and source['event'] in ('workflow_run', 'workflow_dispatch')
            and source['head_branch'] == api('')['default_branch'], 'Recovery evidence must come from the trusted default-branch healing workflow')
    print('Trusted recovery workflow and exact candidate SHA verified.')


def probe(args):
    """CI-only: candidate code runs without collector, OpenAI or write credentials."""
    require(all(not os.environ.get(k) for k in ('OPENAI_API_KEY', 'TOGETHER_API_KEY', 'FIREWORKS_API_KEY', 'GOOGLE_CLOUD_BILLING_API_KEY', 'GH_TOKEN')), 'Replay requires a secret-free test environment')
    evidence = load(args.directory / 'evidence.json')
    provider = evidence['provider']
    module = importlib.import_module('providers.' + provider)
    from scripts.normalize import catalog
    _, aliases = catalog()
    body = evidence['source_payload']
    require(hashlib.sha256(body.encode()).hexdigest() == evidence['source_sha256'], 'Replay source hash mismatch')
    if provider in ('gemini', 'vertex', 'azure'):
        result = module.parse(body, aliases, datetime.fromisoformat(evidence['observed_at'].replace('Z', '+00:00')).date())
    else:
        result = module.parse(body, aliases)
    require(not result.parse_error and result.authoritative_catalog == evidence['authoritative_catalog'], 'Replay changed snapshot/removal semantics')
    require(result.source_payload == body and result.source_sha256 == evidence['source_sha256']
            and result.source_url == evidence['source_url'], 'Replay changed source provenance')
    require(normalized_quotes(provider, result.records, evidence['observed_at'], evidence['source_sha256']) == evidence['expected'],
            'Replay changed reviewed prices, currencies, identities, units, tiers, regions or token bands; human review required')
    run_id = identifier(evidence['failed_run_id'])
    test = 'test_recovery_{}.py'.format(run_id)
    require((ROOT / 'tests' / test).is_file(), 'New regression test is missing')
    with tempfile.TemporaryDirectory(prefix='token3-recovery-regression-') as directory:
        scratch = Path(directory)
        for name in ('providers', 'scripts', 'catalog', 'tests'):
            shutil.copytree(ROOT / name, scratch / name, ignore=shutil.ignore_patterns('__pycache__'))
        (scratch / PARSERS[provider]).write_text(evidence['base_parser'])
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', test, '-v'],
                                cwd=scratch, capture_output=True, text=True, timeout=120)
        require(result.returncode != 0 and re.search(r'Ran [1-9][0-9]* tests?', result.stderr)
                and 'FAILED (' in result.stderr and not re.search(r'ImportError|ModuleNotFoundError|SyntaxError', result.stderr),
                'Regression must fail on the original parser, not due to import/syntax errors')
    print('Recovery replay preserves all reviewed quotes; regression fails against the original parser.')


def verify_candidate(candidate, proposal, evidence):
    contents = validate_proposal(proposal, evidence)
    head = commit_sha(candidate['head_sha']); identifier(candidate['ci_run_id'], 'CI run ID')
    require(candidate['base_sha'] == evidence['base_sha'] and candidate['branch'] == 'self-heal/collection-' + evidence['failed_run_id'], 'Candidate identity changed')
    require(api('/branches/' + evidence['default_branch'])['protected'] is False,
            'Protected/ruleset-governed default branches require a policy-aware human/App merge; indirect auto-merge is prohibited')
    pr = api('/pulls/' + str(candidate['pr']))
    require(pr['state'] == 'open' and not pr['draft'] and pr['user']['login'] == BOT, 'PR is not an open bot-authored recovery')
    require(pr['head']['repo']['full_name'] == repository() and pr['head']['ref'] == candidate['branch']
            and pr['head']['sha'] == head and pr['base']['ref'] == evidence['default_branch'], 'PR head/base/repository changed')
    require(branch_sha(evidence['default_branch']) == evidence['base_sha'] and branch_sha(candidate['branch']) == head, 'Base or recovery branch moved; new review required')
    comparison = api('/compare/{}...{}'.format(evidence['base_sha'], head))
    require(comparison['total_commits'] == 1 and len(comparison['files']) == len(contents), 'Repair history or file set changed')
    actual = {}
    for file in comparison['files']:
        path = file['filename']
        require(path in contents and file['status'] in ('added', 'modified'), 'Unexpected path/deletion/rename')
        require((file['status'] == 'modified') == (path == PARSERS[evidence['provider']]), 'Existing tests or fixtures were modified')
        blob = api('/git/blobs/' + file['sha'])
        require(blob['size'] <= 128 * 1024 and blob['encoding'] == 'base64', 'Invalid PR blob')
        actual[path] = base64.b64decode(blob['content']).decode('utf-8')
    require(actual == contents and digest(actual) == candidate['proposal_sha256'], 'PR contents do not match the approved proposal')
    # A blob can also be a symlink; Git tree mode must be ordinary non-executable files.
    tree = api('/git/trees/{}?recursive=1'.format(head))
    require(not tree['truncated'], 'Cannot validate the full candidate tree')
    modes = {f['path']: (f['mode'], f['type']) for f in tree['tree']}
    require(all(modes.get(path) == ('100644', 'blob') for path in contents), 'Non-regular/executable repair files are prohibited')
    run = api('/actions/runs/' + candidate['ci_run_id'])
    ci_run_valid(run, candidate, evidence, api('/actions/workflows/ci.yml')['id'])
    jobs = api('/actions/runs/{}/jobs'.format(candidate['ci_run_id']))['jobs']
    require(len(jobs) == 1 and jobs[0]['name'] == 'check' and jobs[0]['conclusion'] == 'success', 'Required CI job is missing/failed')
    return commit_sha(tree['sha'])


def merge_verified(candidate, evidence, tree_sha):
    # REST PR merge protects the head but has no expected-base parameter. Build
    # a normal two-parent merge with EXACTLY the tested tree, then fast-forward
    # main without force. A concurrently advanced main is not an ancestor of
    # this frozen merge and GitHub atomically refuses the update. GitHub marks
    # the PR merged when its head becomes an ancestor of its target branch.
    merged = api('/git/commits', 'POST', {'message': 'Merge pull request #{}: bounded {} parser recovery'.format(candidate['pr'], evidence['provider']),
        'tree': commit_sha(tree_sha), 'parents': [evidence['base_sha'], candidate['head_sha']]})
    sha = commit_sha(merged['sha'])
    pr = api('/pulls/' + str(candidate['pr']))
    require(pr['state'] == 'open' and pr['head']['sha'] == candidate['head_sha'], 'PR changed before merge')
    require(branch_sha(evidence['default_branch']) == evidence['base_sha'], 'Default branch changed before merge')
    require(api('/branches/' + evidence['default_branch'])['protected'] is False, 'Default branch protection changed; automatic merge prohibited')
    api('/git/refs/heads/' + evidence['default_branch'], 'PATCH', {'sha': sha, 'force': False})
    for _ in range(12):
        pr = api('/pulls/' + str(candidate['pr']))
        if pr['merged']:
            require(pr['head']['sha'] == candidate['head_sha'], 'PR head changed during merge')
            return sha
        time.sleep(5)
    raise ValueError('Tested merge was pushed but GitHub has not confirmed PR merge; manual verification required')


def makeup(evidence, merge_sha):
    run_id = evidence['failed_run_id']
    comment(evidence['issue'], 'Dispatching one replacement collection after recovery. Replacement failures are manual escalation, never another AI loop.')
    run = dispatch_and_wait('collect.yml', evidence['default_branch'], {'recovery_origin_run_id': run_id}, merge_sha,
                            'Replacement collection for daily run ' + run_id, timeout=1200, notify_issue=evidence['issue'])
    comment(evidence['issue'], 'Replacement collection: {} — **{}**.'.format(run['html_url'], run['conclusion']))
    if run['conclusion'] == 'success':
        api('/issues/' + str(evidence['issue']), 'PATCH', {'state': 'closed', 'state_reason': 'completed'})
    else:
        raise ValueError('Replacement collection failed; manual intervention required')


def finish(args):
    evidence = load(args.directory / 'evidence.json')
    if evidence['mode'] == 'retry':
        makeup(evidence, branch_sha(evidence['default_branch'])); return
    if evidence['mode'] != 'repair':
        raise ValueError(evidence['reason'])
    for name in ('proposal.json', 'candidate.json', 'review.json'):
        require((args.directory / name).is_file(), 'Recovery stage did not produce ' + name + '. Check job logs; no merge is authorized.')
    candidate, proposal, review = [load(args.directory / name) for name in ('candidate.json', 'proposal.json', 'review.json')]
    review_approved(review, candidate)
    tree_sha = verify_candidate(candidate, proposal, evidence)
    review_url = 'https://github.com/{}/actions/runs/{}'.format(repository(), os.environ['GITHUB_RUN_ID'])
    api('/statuses/' + candidate['head_sha'], 'POST', {'state': 'success', 'context': 'self-heal/independent-review',
        'description': 'Independent read-only AI review approved this tested commit', 'target_url': review_url})
    comment(candidate['pr'], '**Independent AI review approved** `{}` after [recovery CI]({}).\n\n{}\n\nSafety policy/replay revalidated before merge. This is an independent review gate, not a formal self-approval by the PR-author bot.'.format(
        candidate['head_sha'], 'https://github.com/{}/actions/runs/{}'.format(repository(), candidate['ci_run_id']), review['reason']))
    merge_sha = merge_verified(candidate, evidence, tree_sha)
    comment(evidence['issue'], 'Parser repair merged: https://github.com/{}/pull/{}.'.format(repository(), candidate['pr']))
    makeup(evidence, merge_sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['collect-context', 'prepare', 'publish', 'ci-context', 'probe', 'finish'])
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    try:
        globals()[args.command.replace('-', '_')](args)
    except Exception as exc:
        # Agent/source output is never evaluated or expanded. Only a bounded,
        # JSON-escaped diagnostic is exposed in Actions logs/issue comments.
        message = str(exc)[:1000]
        for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'OPENAI_API_KEY'):
            if os.environ.get(key):
                message = message.replace(os.environ[key], '[redacted]')
        if args.command in ('prepare', 'finish') and (args.directory / 'evidence.json').exists():
            evidence = load(args.directory / 'evidence.json')
            if evidence.get('issue'):
                comment(evidence['issue'], '**Recovery stopped; manual intervention required.**\n\n```json\n' + json.dumps(message).replace('`', '\\u0060') + '\n```')
        print('Recovery stopped: ' + json.dumps(message))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
