"""Recover conservatively aligned PDF rate candidates into research only.

Original PDF assertions are unchanged. Layout-derived candidates are unreviewed,
not native structured quotes and never a public/current pricing projection.
"""
import argparse
import io
import json
from pathlib import Path
import re

from pypdf import PdfReader

from .historical_ledger import DEFAULT_ROOT, canonical, read_asset, read_snapshot, sha
from .historical_sources import decoded


def layout_rates(text, state=None):
    """Require explicit table/units; dual amounts additionally need Input/Output."""
    state = {} if state is None else state
    active, section, unit, dual = (state.get(k) for k in ('active', 'section', 'unit', 'dual'))
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Table "):
            active = "Table 6(a):" in stripped and "Cortex" in stripped
            section = stripped
            unit = None
            dual = False
        if not active:
            continue
        if "Snowflake-managed compute (Credits per one million Tokens)" in line:
            unit = "Credits per one million Tokens"
        elif "Snowflake-managed compute (AI Credits per one million Tokens)" in line:
            unit = "AI Credits per one million Tokens"
        if re.fullmatch(r'Input\s{2,}Output', stripped):
            dual = True
        if stripped == "Legacy Features":
            section = "Table 6(a): Legacy Features"
        feature = r'((?:Cortex (?:Complete|Embed Text \d+)|AI Complete|AI_COMPLETE|AI_EMBED)\s*[–-]\s*.+?)'
        if dual:
            match = re.fullmatch(r'\s*' + feature + r'\s{2,}(\d+(?:\.\d+)?|N/A|-)\s{2,}(\d+(?:\.\d+)?|N/A|-)\s*', line)
            if unit and match and not re.search(r'\s{2,}', match[1]) and any(re.fullmatch(r'\d+(?:\.\d+)?', v) for v in match.groups()[1:]):
                yield dict(feature=match[1], rates=[dict(column=label, amount=value if value not in {'N/A', '-'} else None, source_cell=value)
                    for label, value in zip(('Input', 'Output'), match.groups()[1:])], unit=unit, section=section, source_line=line)
        else:
            match = re.fullmatch(r'\s*' + feature + r'\s{2,}(\d+(?:\.\d+)?)\s*', line)
            if unit and match and not re.search(r'\s{2,}', match[1]):
                yield dict(feature=match[1], amount=match[2], unit=unit, section=section, source_line=line)
    state.update(active=active, section=section, unit=unit, dual=dual)


def single_column_rates(text):
    yield from (row for row in layout_rates(text) if 'amount' in row)


def capture_candidates(capture, raw):
    if capture['source_kind'] == 'commoncrawl_native_v4':
        from .historical_commoncrawl import payload, truncation
        if truncation(raw):
            return
        raw = payload(capture, raw)
    content = decoded(raw)
    if not content.startswith(b"%PDF"):
        return
    reader = PdfReader(io.BytesIO(content))
    if reader.is_encrypted or len(reader.pages) > 100:
        return
    state = {}
    for number, page in enumerate(reader.pages, 1):
        for row in layout_rates(page.extract_text(extraction_mode="layout") or "", state):
            candidate = dict(provider="snowflake", capture_id=capture["id"], source_sha256=capture["raw"]["content_sha256"],
                source_url=capture["source_url"], replay_url=capture["replay_url"], archive_capture_at=capture["archive_capture_at"],
                source_published_at=capture["source_published_at"], effective_at=None, page=number,
                comparison_eligible=False, review_status="unreviewed_layout_candidate", currency=None, **row)
            candidate["id"] = sha(canonical(candidate))
            yield candidate


def audit(root, *, snapshot=None):
    manifest, rows, snapshot_sha256 = read_snapshot(root) if snapshot is None else snapshot
    candidates, captures = [], []
    for capture in rows:
        if capture["kind"] != "capture" or capture["provider"] != "snowflake" or capture["source_kind"] not in {"archived_native_v2", "arquivo_native_v3", "commoncrawl_native_v4"}:
            continue
        raw = read_asset(root, capture["raw"], "sources")
        from .historical_commoncrawl import payload, truncation
        if capture['source_kind'] == 'commoncrawl_native_v4' and truncation(raw):
            continue
        content = payload(capture, raw) if capture['source_kind'] == 'commoncrawl_native_v4' else raw
        if not decoded(content).startswith(b"%PDF"):
            continue
        recovered = list(capture_candidates(capture, raw))
        candidates.extend(recovered)
        count = len(recovered)
        captures.append(dict(capture_id=capture["id"], candidate_count=count,
            state="layout_candidates" if count else "no_supported_aligned_table"))
    return dict(schema_version=1, policy="historical-pdf-layout-research-v1", ledger_manifest_sha256=snapshot_sha256,
        candidates=candidates, captures=captures, limitation="Table 6(a) only; dual rates require explicit Input/Output headers. Credits and AI Credits remain distinct. Feature text may retain attached PDF footnote markers; exact API identity and full tariff conditions remain unreviewed. No currency conversion, effective-date inference or review promotion.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger-dir", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.ledger_dir)
    args.output.write_bytes(canonical(result) + b"\n")
    print(json.dumps(dict(captures=len(result["captures"]), candidates=len(result["candidates"]))))


if __name__ == "__main__":
    main()
