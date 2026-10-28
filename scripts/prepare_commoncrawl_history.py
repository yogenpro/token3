"""Offline preflight for retained exact public Common Crawl ranges."""
import argparse
from collections import Counter
import json
from pathlib import Path

from .discover_historical_evidence import _body_for_receipt, save
from .historical_ledger import asset, canonical, record, sha
from .historical_profiles import PROFILE
from .historical_sources import archive_time, extract


def prepare(stage):
    plan = json.loads((stage / 'plan.json').read_bytes())
    if plan.get('archive') != 'commoncrawl' or plan.get('profile') != PROFILE:
        raise ValueError('Unsupported Common Crawl stage')
    sources, checks, labels, context, stats, rejections = [], [], {}, {}, Counter(), []

    def accept(label, metadata, receipt):
        raw = _body_for_receipt(stage, receipt)
        scope = dict(metadata['request_scope'])
        requested = 'bytes {}-{}'.format(scope['byte_start'], scope['byte_start'] + scope['byte_length'] - 1)
        expected_url = metadata['source_url'] if metadata['source_kind'] == 'commoncrawl_index_v4' else scope['retrieval_url']
        if (receipt.get('state') != 'retrieved' or receipt.get('http_status') != 206 or receipt['url'] != expected_url or
                not receipt.get('content_range', '').startswith(requested + '/') or
                len(raw) != scope['byte_length'] or metadata['retrieved_at'] != receipt['retrieved_at']):
            raise ValueError('Common Crawl receipt does not prove the selected response range')
        if 'index_label' in scope:
            scope['index_capture_id'] = labels[scope.pop('index_label')]
        capture = record(dict(kind='capture', **dict(metadata, request_scope=scope), raw=asset(raw, 'sources')[0]))
        assertions, coverage = extract(capture, raw, context)
        context[capture['id']] = capture, raw
        labels[label] = capture['id']
        sources.append(dict(label=label, metadata=metadata, body_path=receipt['body_path'], body_sha256=receipt['body_sha256']))
        stats['assertions'] += len(assertions); stats['state_' + coverage['state']] += 1

    for index in plan['indexes']:
        accept(index['label'], index['metadata'], index['receipt'])
    for job in plan['jobs']:
        receipt, state = job['receipt'], job['receipt']['state']
        if state == 'retrieved':
            metadata = dict(provider=job['provider'], source_kind='commoncrawl_native_v4', source_url=job['url'], replay_url=None,
                retrieved_at=receipt['retrieved_at'], archive_capture_at=archive_time(job['stamp']), archive_digest=job['digest'],
                source_published_at=None, request_scope=dict(profile=PROFILE, archive='commoncrawl', index_label=job['index_label'],
                    storage_url=job['storage_url'], retrieval_url=receipt['url'], byte_start=job['byte_start'], byte_length=job['byte_length']))
            try:
                accept(job['label'], metadata, receipt)
                continue
            except (ValueError, TypeError, UnicodeError, KeyError, OSError) as exc:
                state = 'extractor_rejected'
                rejections.append(dict(provider=job['provider'], stamp=job['stamp'], source_url=job['url'],
                                       reason_class=type(exc).__name__, reason=str(exc)[:300]))
        checks.append(dict(kind='coverage', capture_id=None, provider=job['provider'], profile=PROFILE, provenance='historical_discovery_v4',
            source_url=receipt['url'], target_url=job['url'], checked_at=receipt.get('checked_at') or receipt['retrieved_at'], state=state,
            http_status=receipt.get('http_status'), transport_exit_code=None, comparison_eligible=False,
            archive_capture_at=archive_time(job['stamp']), archive_digest=job['digest'], index_label=job['index_label'],
            byte_start=job['byte_start'], byte_length=job['byte_length']))
    save(stage / 'validated-sources.json', dict(schema_version=1, sources=sources))
    save(stage / 'validated-checks.json', checks)
    report = dict(profile=PROFILE, archive='commoncrawl', planned_targets=len(plan['jobs']), accepted_captures=len(sources),
                  unresolved_replay_targets=len(checks), states=dict(Counter(c['state'] for c in checks)), rejections=rejections, **stats)
    save(stage / 'coverage-report.json', report)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage-dir', type=Path, required=True)
    a = p.parse_args(); print(json.dumps(prepare(a.stage_dir)))


if __name__ == '__main__':
    main()
