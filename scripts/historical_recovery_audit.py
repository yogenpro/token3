"""Account for every selected replay target against a verified ledger snapshot."""
from collections import Counter, defaultdict
import base64
import hashlib
import json
from pathlib import Path

from .discover_historical_evidence import replay_receipt, _body_for_receipt
from .historical_ledger import canonical, sha
from .historical_profiles import source_spec
from .historical_sources import archive_time, public_source


def archive_namespace(row):
    if row.get('source_kind', '').startswith('arquivo_') or row.get('provenance') == 'historical_discovery_v3':
        return 'arquivo.pt'
    if row.get('source_kind', '').startswith('commoncrawl_') or row.get('provenance') == 'historical_discovery_v4':
        return 'commoncrawl'
    return 'web.archive.org'


def build(snapshot, stages, baseline_checks=None):
    manifest, rows, snapshot_sha256 = snapshot
    retained = {(archive_namespace(r), r['provider'], r['archive_capture_at'], r['source_url'], r['archive_digest']) for r in rows
                if r['kind'] == 'capture' and r['archive_digest'] is not None}
    payloads = defaultdict(list)
    points = defaultdict(list)
    for r in rows:
        if r['kind'] == 'capture' and r['archive_digest']:
            payloads[r['provider'], r['archive_digest']].append(r['id'])
            points[r['provider'], r['archive_capture_at'], r['source_url'], r['archive_digest']].append(r['id'])
    baseline = json.loads(Path(baseline_checks).read_bytes()) if baseline_checks else []
    baseline_keys = {('web.archive.org', r['provider'], r['archive_capture_at'], r['target_url'], r['archive_digest']) for r in baseline if r.get('archive_capture_at')}
    plans, missing, providers = [], [], defaultdict(Counter)
    for directory in stages:
        root = Path(directory)
        plan_bytes = (root / 'plan.json').read_bytes()
        plan = json.loads(plan_bytes)
        namespace = plan.get('archive', 'web.archive.org')
        check_file = root / 'validated-checks.json'
        checks = json.loads(check_file.read_bytes()) if check_file.exists() else []
        rejected = {(r['provider'], r['archive_capture_at'], r['target_url'], r['archive_digest']): r['state']
                    for r in checks if r.get('archive_capture_at')}
        counts = Counter()
        for job in plan['jobs']:
            if job['provider'] == 'deepinfra' and namespace == 'web.archive.org':
                public_source(job['url'], 'deepinfra')
            else:
                source_spec(job['url'], job['provider'])
            key = (namespace, job['provider'], archive_time(job['stamp']), job['url'], job['digest'])
            providers[job['provider']]['planned_targets'] += 1
            if key in retained:
                counts['retained'] += 1
                providers[job['provider']]['retained_targets'] += 1
                continue
            if namespace == 'commoncrawl':
                url, receipt = job['receipt']['url'], job['receipt']
            elif namespace == 'arquivo.pt':
                from .historical_arquivo import replay
                url = replay(job['stamp'], job['url'])
            else:
                url = 'https://web.archive.org/web/' + job['stamp'] + 'id_/' + job['url']
            if namespace != 'commoncrawl':
                receipt = replay_receipt(root, job['provider'], url, job['digest'])
            state, http = receipt['state'], receipt.get('http_status')
            if state == 'fetch_failed':
                state = 'transport_failed' if http is None else 'redirect_denied' if 300 <= http < 400 else 'http_failed'
            elif state == 'retrieved':
                body = _body_for_receipt(root, receipt)
                state = rejected.get(key[1:], 'staged_not_retained') if namespace == 'commoncrawl' else (
                    'staged_not_retained' if base64.b32encode(hashlib.sha1(body).digest()).decode() == job['digest'] else 'digest_mismatch')
            counts[state] += 1
            providers[job['provider']][state] += 1
            missing.append(dict(provider=job['provider'], archive=namespace, archive_capture_at=key[2], source_url=job['url'],
                replay_url=None if namespace == 'commoncrawl' else url, archive_fetch_url=url,
                archive_digest=job['digest'], state=state, http_status=http, attempts=receipt.get('attempts', 0),
                checked_at=receipt.get('checked_at'), receipt_record_sha256=sha(canonical(receipt)),
                matching_retained_payload_capture_ids=payloads.get((job['provider'], job['digest']), []),
                same_point_retained_capture_ids=points.get(key[1:], []),
                in_original_backlog=key in baseline_keys))
        plans.append(dict(plan_sha256=sha(plan_bytes), archive=plan.get('archive', 'web.archive.org'),
                          planned_targets=len(plan['jobs']), states=dict(counts)))
    return dict(schema_version=1, policy='historical-recovery-accounting-v1', ledger_manifest_sha256=snapshot_sha256,
        ledger_counts=manifest['counts'], plans=plans,
        original_backlog=dict(targets=len(baseline_keys), retained=len(baseline_keys & retained), unresolved=len(baseline_keys - retained),
                              prior_states=dict(Counter(r['state'] for r in baseline))),
        providers={k: dict(v) for k, v in sorted(providers.items())}, unresolved_targets=missing,
        limitation='Selected exact URL/timestamp/digest targets only. Completed queues do not establish complete provider history, tariff continuity or retirement.')
