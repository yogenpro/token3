"""Bounded, content-addressed derivative research reports; never warehouse writes."""
from pathlib import Path

from .historical_ledger import MAX_BYTES, _atomic, _immutable, asset, canonical, read_asset
from .historical_sources import json_source


def write_report(path, document):
    path = Path(path)
    # Small research reports remain directly inspectable.
    raw = canonical(document) + b'\n'
    if len(raw) <= 4 * 1024 * 1024:
        _atomic(path, raw)
        return
    root = path.parent / (path.stem + '-assets')
    root.mkdir(exist_ok=True)
    refs, chunk, count = [], bytearray(), 0

    def flush():
        ref, encoded = asset(bytes(chunk), 'segments')
        ref['record_count'] = count
        _immutable(root, ref, encoded)
        refs.append(ref)

    for candidate in document['candidates']:
        line = canonical(candidate) + b'\n'
        if len(line) > MAX_BYTES:
            raise ValueError('Research candidate exceeds segment cap')
        if chunk and len(chunk) + len(line) > MAX_BYTES:
            flush()
            chunk, count = bytearray(), 0
        chunk.extend(line)
        count += 1
    if chunk:
        flush()
    manifest = {k: v for k, v in document.items() if k != 'candidates'}
    manifest.update(candidate_count=len(document['candidates']), candidate_assets=root.name, candidate_segments=refs)
    encoded = canonical(manifest) + b'\n'
    if len(encoded) > 4 * 1024 * 1024:
        raise ValueError('Research manifest exceeds cap')
    _atomic(path, encoded)


def read_report(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Unsafe or oversized research manifest')
    document = json_source(path.read_bytes())
    if 'candidates' in document:
        return document
    if document.get('candidate_assets') != path.stem + '-assets':
        raise ValueError('Research asset directory differs')
    root = path.parent / document['candidate_assets']
    if root.is_symlink():
        raise ValueError('Research assets cannot be symlinked')
    candidates, seen = [], set()
    for ref in document['candidate_segments']:
        if ref['path'] in seen:
            raise ValueError('Duplicate research segment')
        seen.add(ref['path'])
        raw = read_asset(root, ref, 'segments')
        lines = raw.splitlines()
        if not raw.endswith(b'\n') or len(lines) != ref['record_count']:
            raise ValueError('Incomplete research segment')
        candidates.extend(json_source(line) for line in lines)
    if len(candidates) != document['candidate_count']:
        raise ValueError('Incomplete research report')
    return {k: v for k, v in document.items() if k not in {'candidate_count', 'candidate_assets', 'candidate_segments'}} | {'candidates': candidates}
