"""Retain licensed community history as attributed research, never vendor observations."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
import re

from .historical_ledger import MAX_BYTES, _immutable, asset, canonical, sha
from .historical_research_files import write_report
from .historical_sources import timestamp, json_source

FILES = {
    'llerandi/llm-price-tracker': {'LICENSE', 'README.md', 'data/history_summary.json'},
    'romanshumy/llm-prices-data': {'LICENSE-DATA.md', 'README.md', 'price-history.json'},
}


def prepare(stage, output):
    receipts = json.loads((stage / 'receipts.json').read_bytes())
    sources, bodies, seen = [], {}, set()
    for r in receipts:
        repo, name, commit = r['repo'], r['file'], r['commit']
        if (repo not in FILES or name not in FILES[repo] or (repo, name) in seen or
                not re.fullmatch(r'[a-f0-9]{40}', commit) or r['http_status'] != 200 or
                r['url'] != 'https://raw.githubusercontent.com/' + repo + '/' + commit + '/' + name or
                r['body_path'] != r['sha256'] or not re.fullmatch(r'[a-f0-9]{64}', r['sha256'])):
            raise ValueError('Unsupported community source receipt')
        path = stage / r['body_path']
        if path.is_symlink() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError('Unsafe community source body')
        raw = path.read_bytes()
        if len(raw) != r['bytes'] or sha(raw) != r['sha256']:
            raise ValueError('Community source hash/bytes differ')
        timestamp(r['retrieved_at'])
        seen.add((repo, name)); bodies[repo, name] = raw
        sources.append(dict(repo=repo, file=name, commit=commit, source_url=r['url'], retrieved_at=r['retrieved_at'],
                            source_sha256=sha(raw), raw=asset(raw, 'sources')[0]))
    if seen != {(repo, name) for repo, names in FILES.items() for name in names}:
        raise ValueError('Incomplete community source/license bundle')
    for repo in FILES:
        if len({s['commit'] for s in sources if s['repo'] == repo}) != 1:
            raise ValueError('Community bundle spans different commits')
    mit = bodies['llerandi/llm-price-tracker', 'LICENSE'].decode()
    cc = bodies['romanshumy/llm-prices-data', 'LICENSE-DATA.md'].decode()
    if 'MIT License' not in mit or 'Copyright (c) 2026 Llerandi' not in mit or 'CC BY 4.0' not in cc or 'modelpricewatch.com' not in cc:
        raise ValueError('Community data license needs separate review')
    candidates, stats = [], {}
    for source in sources:
        if not source['file'].endswith('.json'):
            continue
        data = json_source(bodies[source['repo'], source['file']])
        if source['repo'] == 'llerandi/llm-price-tracker':
            dates, models = data['dates'], data['models']
            if dates != sorted(set(dates)):
                raise ValueError('Ambiguous community date axis')
            for model in models.values():
                if len(model['input']) != len(dates) or len(model['output']) != len(dates):
                    raise ValueError('Incomplete community price/date alignment')
            record_dates = lambda model: dates
        else:
            models = data
            record_dates = lambda model: [r['date'] for r in model['history']]
        all_dates, labels, dated_records = [], Counter(), 0
        for key, model in models.items():
            days = record_dates(model)
            for day in days:
                if date.fromisoformat(day) > timestamp(source['retrieved_at']).date():
                    raise ValueError('Community date follows retrieval')
            all_dates.extend(days); dated_records += len(days); labels[model['provider']] += 1
            row = dict(source_repo=source['repo'], source_sha256=source['source_sha256'], source_local_model_key=key,
                reported_provider=model['provider'], native_provider=None, native_id=None,
                date_axis=days if source['repo'] == 'llerandi/llm-price-tracker' else None,
                source_record=model, review_status='unreviewed_community_report', comparison_eligible=False,
                date_basis='publisher-reported date; not independently observed or tariff-effective')
            candidates.append(dict(row, id=sha(canonical(row))))
        stats[source['repo']] = dict(model_records=len(models), publisher_dated_records=dated_records,
            reported_provider_labels=dict(sorted(labels.items())), earliest_reported_day=min(all_dates), latest_reported_day=max(all_dates))
    document = dict(schema_version=1, policy='historical-community-research-v1', sources=sources, candidates=candidates,
        statistics=stats, attribution=[dict(publisher='Llerandi', license='MIT', notice=mit),
            dict(publisher='modelpricewatch.com', license='CC BY 4.0', notice=cc,
                 license_url='https://creativecommons.org/licenses/by/4.0/')],
        notes=['Exact commit-pinned source bytes retained; decimal literals retained as strings without economic normalization.',
               'Dates and model keys are publisher assertions, not provider observations, exact native identities or launch dates.',
               'Repeated daily values are source records, not distinct price changes. No provider equivalence is inferred.',
               'Outside native ledger, public projections, reviewed quotes and current comparisons.'])
    # Validate the whole bundle before writing any immutable research assets.
    root = output.parent / (output.stem + '-assets'); root.mkdir(parents=True, exist_ok=True)
    for source in sources:
        ref, encoded = asset(bodies[source['repo'], source['file']], 'sources')
        _immutable(root, ref, encoded)
    write_report(output, document)
    return stats


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.stage_dir, a.output)))


if __name__ == '__main__':
    main()
