"""Bounded public Common Crawl CDX-block/WARC witnesses, without paid query services."""
import base64
import gzip
import hashlib
import io
import re
import zlib
from datetime import timezone

from .historical_profiles import PROFILE, source_spec
from .historical_sources import MAX_BYTES, json_source, timestamp

KINDS = {'commoncrawl_index_v4', 'commoncrawl_native_v4'}
COLLECTION = r'CC-MAIN-20[0-9]{2}-[0-9]{2}'
INDEX = re.compile(r'https://data\.commoncrawl\.org/cc-index/collections/(' + COLLECTION + r')/indexes/cdx-[0-9]{5}\.gz')
WARC = re.compile(r'https://data\.commoncrawl\.org/crawl-data/(' + COLLECTION + r')/segments/[0-9]+\.[0-9]+/warc/CC-MAIN-[0-9]{14}-[0-9]{14}-[0-9]{5}\.warc\.gz')


def uncompress(raw):
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:
            body = f.read(MAX_BYTES + 1)
    except (gzip.BadGzipFile, EOFError, zlib.error) as exc:
        raise ValueError('Invalid Common Crawl gzip member') from exc
    if not body or len(body) > MAX_BYTES:
        raise ValueError('Empty or oversized Common Crawl member')
    return body


def range_scope(scope, raw=None):
    if (type(scope.get('byte_start')) is not int or scope['byte_start'] < 0 or
            type(scope.get('byte_length')) is not int or not 0 < scope['byte_length'] <= MAX_BYTES or
            (raw is not None and len(raw) != scope['byte_length'])):
        raise ValueError('Invalid Common Crawl byte-range scope')


def validate_capture(capture):
    scope, kind = capture['request_scope'], capture['source_kind']
    retrieved = timestamp(capture['retrieved_at'])
    if kind not in KINDS or scope.get('profile') != PROFILE or scope.get('archive') != 'commoncrawl':
        raise ValueError('Unsupported Common Crawl profile')
    range_scope(scope)
    if capture['source_published_at'] is not None or capture['replay_url'] is not None:
        raise ValueError('Common Crawl does not infer publication or a browser replay')
    if kind == 'commoncrawl_index_v4':
        if (set(scope) != {'profile', 'archive', 'target_url', 'byte_start', 'byte_length'} or
                not INDEX.fullmatch(capture['source_url']) or capture['archive_capture_at'] is not None or capture['archive_digest'] is not None):
            raise ValueError('Invalid Common Crawl index metadata')
        source_spec(scope['target_url'], capture['provider'])
    else:
        source_spec(capture['source_url'], capture['provider'])
        if (set(scope) - {'retrieval_url'} != {'profile', 'archive', 'index_capture_id', 'storage_url', 'byte_start', 'byte_length'} or
                not WARC.fullmatch(scope['storage_url']) or not re.fullmatch(r'capture-[a-f0-9]{64}', scope['index_capture_id']) or
                timestamp(capture['archive_capture_at']) > retrieved or not re.fullmatch(r'[A-Z2-7]{32}', capture['archive_digest'])):
            raise ValueError('Invalid Common Crawl WARC metadata')
        if scope.get('retrieval_url', scope['storage_url']) not in retrieval_urls(scope['storage_url']):
            raise ValueError('Unapproved Common Crawl retrieval location')


def retrieval_urls(storage):
    return {storage, storage.replace('https://data.commoncrawl.org/', 'https://huggingface.co/buckets/commoncrawl/commoncrawl/resolve/', 1)}


def index_entries(capture, raw):
    range_scope(capture['request_scope'], raw)
    rows = []
    for line in uncompress(raw).splitlines():
        _, stamp, data = line.decode('utf-8').split(' ', 2)
        row = json_source(data.encode('utf-8'))
        if row.get('status') != '200' or row.get('url') != capture['request_scope']['target_url']:
            continue
        if not re.fullmatch(r'\d{14}', stamp) or not re.fullmatch(r'[A-Z2-7]{32}', row.get('digest', '')):
            raise ValueError('Malformed selected Common Crawl CDX entry')
        row = dict(row, stamp=stamp)
        storage = 'https://data.commoncrawl.org/' + row['filename']
        if (not WARC.fullmatch(storage) or INDEX.fullmatch(capture['source_url'])[1] != WARC.fullmatch(storage)[1] or
                not str(row['offset']).isdigit() or not str(row['length']).isdigit() or not 0 < int(row['length']) <= MAX_BYTES):
            raise ValueError('Invalid Common Crawl storage witness')
        rows.append(row)
    if not rows:
        raise ValueError('Common Crawl block lacks selected successful entries')
    return rows


def headers(raw):
    if len(raw) > 65536:
        raise ValueError('Oversized WARC headers')
    lines = raw.split(b'\r\n'); result = {}
    for line in lines[1:]:
        name, value = line.split(b':', 1); name = name.decode('ascii').lower()
        if name in result and name in {'content-length', 'warc-type', 'warc-target-uri', 'warc-date', 'warc-payload-digest', 'warc-block-digest'}:
            raise ValueError('Duplicate archive/HTTP header')
        result[name] = value.strip().decode('utf-8')
    return lines[0], result


def payload(capture, raw):
    range_scope(capture['request_scope'], raw)
    body = uncompress(raw)
    head, block = body.split(b'\r\n\r\n', 1)
    version, meta = headers(head)
    size = int(meta['content-length'])
    if (version not in {b'WARC/1.0', b'WARC/1.1'} or meta['warc-type'] != 'response' or
            meta['warc-target-uri'] != capture['source_url'] or timestamp(meta['warc-date']) != timestamp(capture['archive_capture_at']) or
            meta['warc-payload-digest'].upper() != 'SHA1:' + capture['archive_digest'] or
            not 0 < size <= MAX_BYTES or len(block) < size or block[size:].strip(b'\r\n')):
        raise ValueError('Common Crawl WARC date/URL/type/digest/length differs')
    http, data = block[:size].split(b'\r\n\r\n', 1)
    if 'warc-block-digest' in meta and meta['warc-block-digest'].upper() != 'SHA1:' + base64.b32encode(hashlib.sha1(block[:size]).digest()).decode():
        raise ValueError('Common Crawl WARC block digest differs')
    status = http.split(b'\r\n', 1)[0].split()
    if len(status) < 2 or status[1] != b'200' or base64.b32encode(hashlib.sha1(data).digest()).decode() != capture['archive_digest']:
        raise ValueError('Common Crawl HTTP payload differs from CDX/WARC digest')
    return data


def truncation(raw):
    _, meta = headers(uncompress(raw).split(b'\r\n\r\n', 1)[0])
    return meta.get('warc-truncated')


def verify_witness(capture, raw, context):
    scope = capture['request_scope']; witness = context.get(scope['index_capture_id'])
    if not witness or witness[0]['source_kind'] != 'commoncrawl_index_v4' or witness[0]['provider'] != capture['provider']:
        raise ValueError('Common Crawl body lacks its retained CDX block')
    stamp = timestamp(capture['archive_capture_at']).astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')
    if not any(r['stamp'] == stamp and r['url'] == capture['source_url'] and r['digest'] == capture['archive_digest'] and
               'https://data.commoncrawl.org/' + r['filename'] == scope['storage_url'] and int(r['offset']) == scope['byte_start'] and
               int(r['length']) == scope['byte_length'] for r in index_entries(witness[0], witness[1])):
        raise ValueError('Common Crawl replay does not match its exact CDX storage witness')
    return payload(capture, raw)


def validate_check(row, context):
    fields = {'kind', 'id', 'capture_id', 'provider', 'profile', 'provenance', 'source_url', 'target_url', 'checked_at', 'state',
              'http_status', 'transport_exit_code', 'comparison_eligible', 'archive_capture_at', 'archive_digest', 'index_capture_id',
              'byte_start', 'byte_length'}
    if (set(row) != fields or row['capture_id'] is not None or row['profile'] != PROFILE or
            row['provenance'] != 'historical_discovery_v4' or row['comparison_eligible'] is not False or row['transport_exit_code'] is not None):
        raise ValueError('Invalid Common Crawl coverage check')
    checked = timestamp(row['checked_at']); range_scope(row); source_spec(row['target_url'], row['provider'])
    if timestamp(row['archive_capture_at']) > checked:
        raise ValueError('Common Crawl target follows its check timestamp')
    status = row['http_status']
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ValueError('Invalid Common Crawl HTTP status')
    if row['state'] not in {'http_failed', 'transport_failed', 'range_mismatch', 'extractor_rejected',
                             'deferred_public_access', 'not_in_published_mirror', 'oversized_archive_record'}:
        raise ValueError('Unsupported Common Crawl check state')
    witness = context.get(row['index_capture_id'])
    stamp = timestamp(row['archive_capture_at']).astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')
    if not witness or witness[0]['source_kind'] != 'commoncrawl_index_v4' or witness[0]['provider'] != row['provider'] or not any(
            r['stamp'] == stamp and r['url'] == row['target_url'] and r['digest'] == row['archive_digest'] and
            row['source_url'] in retrieval_urls('https://data.commoncrawl.org/' + r['filename']) and
            int(r['offset']) == row['byte_start'] and int(r['length']) == row['byte_length'] for r in index_entries(witness[0], witness[1])):
        raise ValueError('Common Crawl failed/deferred target lacks its exact CDX witness')
