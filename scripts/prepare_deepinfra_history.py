"""Preflight remaining DeepInfra replays against its original retained V1 indexes."""
import argparse
import base64
import hashlib
import json
from pathlib import Path

from .discover_historical_evidence import _body_for_receipt, replay_receipt, save
from .historical_ledger import asset, canonical, record
from .historical_sources import archive_time, extract, public_source


def prepare(stage):
    plan = json.loads((stage / 'plan.json').read_bytes())
    if plan.get('profile') != 'historical-native-v1':
        raise ValueError('Unsupported DeepInfra continuation plan')
    sources, context, labels, failures = [], {}, {}, []
    assertions, duplicates = 0, plan.get('duplicate_index_entries', 0)
    seen_jobs = {}
    for i, index in enumerate(plan['indexes']):
        capture = index['capture']
        if capture['provider'] != 'deepinfra' or capture['source_kind'] != 'archive_index' or record(capture) != capture:
            raise ValueError('Continuation requires original DeepInfra index identities')
        raw = _body_for_receipt(stage, index)
        if asset(raw, 'sources')[0] != capture['raw']:
            raise ValueError('Original DeepInfra index bytes differ')
        extract(capture, raw, context)
        context[capture['id']] = (capture, raw)
        label = 'deepinfra-retained-index-' + str(i)
        labels[capture['id']] = label
        meta = {k: v for k, v in capture.items() if k not in {'kind', 'id', 'raw'}}
        sources.append(dict(label=label, metadata=meta, body_path=index['body_path'], body_sha256=index['body_sha256']))
    for job in plan['jobs']:
        key = (job['stamp'], job['url'], job['digest'])
        if key in seen_jobs:
            if seen_jobs[key] != job:
                raise ValueError('Conflicting duplicate DeepInfra target metadata')
            duplicates += 1
            continue
        seen_jobs[key] = job
        public_source(job['url'], 'deepinfra')
        replay = 'https://web.archive.org/web/' + job['stamp'] + 'id_/' + job['url']
        receipt = replay_receipt(stage, 'deepinfra', replay, job['digest'])
        if receipt['state'] != 'retrieved':
            failures.append(dict(job=job, receipt=receipt))
            continue
        raw = _body_for_receipt(stage, receipt)
        if base64.b32encode(hashlib.sha1(raw).digest()).decode() != job['digest']:
            failures.append(dict(job=job, state='digest_mismatch'))
            continue
        scope = dict(index_capture_id=job['index_capture_id'])
        meta = dict(provider='deepinfra', source_kind='deepinfra_html', source_url=job['url'], replay_url=replay,
                    retrieved_at=receipt['retrieved_at'], archive_capture_at=archive_time(job['stamp']), archive_digest=job['digest'],
                    source_published_at=None, request_scope=scope)
        capture = record(dict(kind='capture', raw=asset(raw, 'sources')[0], **meta))
        found, _ = extract(capture, raw, context)
        assertions += len(found)
        meta['request_scope'] = dict(index_label=labels[job['index_capture_id']])
        sources.append(dict(label=job['label'], metadata=meta, body_path=receipt['body_path'], body_sha256=receipt['body_sha256']))
    save(stage / 'validated-sources.json', dict(schema_version=1, sources=sources))
    report = dict(profile='historical-native-v1', planned_replays=len(seen_jobs), duplicate_index_entries=duplicates,
                  accepted_replays=len(sources) - len(plan['indexes']),
                  assertions=assertions, unresolved=failures,
                  limitation='Original DeepInfra index witnesses and extraction semantics; failures are research receipts, never fabricated native observations.')
    save(stage / 'coverage-report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage-dir', type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.stage_dir)
    print(json.dumps({k: v for k, v in report.items() if k != 'unresolved'} | dict(unresolved=len(report['unresolved']))))


if __name__ == '__main__':
    main()
