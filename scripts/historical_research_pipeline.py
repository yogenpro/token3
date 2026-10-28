"""Rebuild independent research audits from one completely verified snapshot."""
import argparse
from datetime import date
import json
from pathlib import Path

from .historical_ledger import DEFAULT_ROOT, read_snapshot
from .historical_embedded_research import audit as embedded_audit
from .historical_pdf_research import audit as pdf_audit
from .historical_price_coverage import build as price_audit
from .historical_recovery_audit import build as recovery_audit
from .historical_research_files import write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger-dir', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--research-day', type=date.fromisoformat, required=True)
    parser.add_argument('--stage-dir', type=Path, action='append', default=[])
    parser.add_argument('--baseline-checks', type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = read_snapshot(args.ledger_dir)
    print(json.dumps(dict(verified_counts=snapshot[0]['counts'])), flush=True)
    paths = {name: args.output_dir / ('historical-recovery-' + name + '-' + args.research_day.isoformat() + '.json')
             for name in ('pdf-prices', 'embedded-prices', 'price-coverage', 'targets')}
    for name, audit in [('pdf-prices', pdf_audit), ('embedded-prices', embedded_audit)]:
        result = audit(args.ledger_dir, snapshot=snapshot)
        write_report(paths[name], result)
        print(json.dumps(dict(report=name, captures=len(result['captures']), candidates=len(result['candidates']))), flush=True)
    result = price_audit(args.ledger_dir, pdf_research=paths['pdf-prices'], embedded_research=paths['embedded-prices'], snapshot=snapshot)
    write_report(paths['price-coverage'], result)
    print(json.dumps(dict(report='price-coverage', statuses={s: sum(p['status'] == s for p in result['providers'].values()) for s in {p['status'] for p in result['providers'].values()}})), flush=True)
    if args.stage_dir:
        result = recovery_audit(snapshot, args.stage_dir, args.baseline_checks)
        write_report(paths['targets'], result)
        print(json.dumps(dict(report='targets', original_backlog=result['original_backlog'], unresolved=len(result['unresolved_targets']))), flush=True)


if __name__ == '__main__':
    main()
