"""Offline preflight for exact Arquivo.pt source indexes and replay receipts."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .discover_historical_evidence import _body_for_receipt, replay_receipt, save
from .historical_arquivo import replay
from .historical_ledger import asset, record
from .historical_profiles import PROFILE
from .historical_sources import archive_time, extract


def prepare(stage):
    plan = json.loads((stage / 'plan.json').read_bytes())
    if plan.get('profile') != PROFILE or plan.get('archive') != 'arquivo.pt':
        raise ValueError('Unsupported Arquivo stage')
    sources, checks, context, labels, stats = [], [], {}, {}, Counter()

    def check(receipt, provider, target, state, job=None):
        row = dict(kind='coverage', capture_id=None, provider=provider, profile=PROFILE, provenance='historical_discovery_v3',
            source_url=replay(job['stamp'], target) if job else receipt['url'], target_url=target,
            checked_at=receipt.get('checked_at') or receipt['retrieved_at'], state=state, http_status=receipt.get('http_status'),
            transport_exit_code=None, comparison_eligible=False, archive_capture_at=archive_time(job['stamp']) if job else None,
            archive_digest=job['digest'] if job else None, index_capture_id=None)
        if job:
            row.pop('index_capture_id')
            row['index_label'] = job['index_label']
        checks.append(row)

    def accept(label, meta, receipt):
        raw = _body_for_receipt(stage, receipt)
        scope = dict(meta['request_scope'])
        if 'index_label' in scope:
            scope['index_capture_id'] = labels[scope.pop('index_label')]
        capture = record(dict(kind='capture', **dict(meta, request_scope=scope), raw=asset(raw, 'sources')[0]))
        assertions, coverage = extract(capture, raw, context)
        context[capture['id']] = (capture, raw)
        labels[label] = capture['id']
        stats['assertions'] += len(assertions)
        stats['captures'] += 1
        stats['state_' + coverage['state']] += 1
        sources.append(dict(label=label, metadata=meta, body_path=receipt['body_path'], body_sha256=receipt['body_sha256']))

    for index in plan['indexes']:
        accept(index['label'], index['metadata'], index['receipt'])
    for receipt in plan['empty_indexes']:
        if receipt.get('http_status') != 200 or receipt.get('body_bytes') != 0:
            raise ValueError('Empty Arquivo lookup must be an actual empty HTTP-200 response')
        check(receipt, receipt['provider'], receipt['target_url'], 'archive_index_empty')
    for job in plan['jobs']:
        url = replay(job['stamp'], job['url'])
        receipt = replay_receipt(stage, job['provider'], url, job['digest'])
        if receipt['state'] != 'retrieved':
            state = receipt['state']
            if state == 'fetch_failed':
                status = receipt.get('http_status')
                state = 'transport_failed' if status is None else 'redirect_denied' if 300 <= status < 400 else 'http_failed'
            check(receipt, job['provider'], job['url'], state, job)
            continue
        meta = dict(provider=job['provider'], source_kind='arquivo_native_v3', source_url=job['url'], replay_url=url,
            retrieved_at=receipt['retrieved_at'], archive_capture_at=archive_time(job['stamp']), archive_digest=job['digest'],
            source_published_at=None, request_scope=dict(profile=PROFILE, archive='arquivo.pt', index_label=job['index_label']))
        try:
            accept(job['label'], meta, receipt)
        except (ValueError, TypeError, UnicodeError, KeyError):
            check(receipt, job['provider'], job['url'], 'extractor_rejected', job)
    if plan.get('rejected'):
        raise ValueError('Unresolved Arquivo index discovery requires investigation before import')
    save(stage / 'validated-sources.json', dict(schema_version=1, sources=sources))
    save(stage / 'validated-checks.json', checks)
    report = dict(profile=PROFILE, archive='arquivo.pt', planned_replays=len(plan['jobs']), accepted_captures=len(sources),
        unresolved_replay_targets=sum(c['archive_capture_at'] is not None for c in checks),
        lookup_states=dict(Counter(c['state'] for c in checks)), **stats)
    save(stage / 'coverage-report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.stage_dir)))


if __name__ == '__main__':
    main()
