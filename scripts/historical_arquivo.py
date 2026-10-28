"""Exact public Arquivo.pt CDX/replay witnesses; no inferred tariff dates."""
import base64
from datetime import timezone
import hashlib
import re
from urllib.parse import parse_qs, urlsplit

from .historical_profiles import PROFILE, source_spec
from .historical_sources import archive_time, decoded, json_source, timestamp

KINDS = {'arquivo_index_v3', 'arquivo_native_v3'}


def query_target(url, provider):
    p = urlsplit(url)
    q = parse_qs(p.query, keep_blank_values=True)
    if (p.scheme != 'https' or p.netloc != 'arquivo.pt' or p.path != '/wayback/cdx' or p.fragment or
            set(q) != {'url', 'matchType', 'output', 'limit', 'to', 'resolveRevisits'} or any(len(v) != 1 for v in q.values()) or
            q['matchType'] != ['exact'] or q['output'] != ['json'] or q['limit'] != ['5001'] or
            q['resolveRevisits'] != ['true'] or not re.fullmatch(r'\d{14}', q['to'][0])):
        raise ValueError('Unsupported Arquivo query')
    source_spec(q['url'][0], provider)
    return q['url'][0]


def replay(stamp, url):
    archive_time(stamp)
    return 'https://arquivo.pt/noFrame/replay/' + stamp + 'id_/' + url


def entries(raw):
    lines = decoded(raw).splitlines()
    if not lines or len(lines) > 5001:
        raise ValueError('Empty or oversized Arquivo index')
    rows = [json_source(line) for line in lines]
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('url'), str) or
                not isinstance(row.get('timestamp'), str) or not re.fullmatch(r'\d{1,14}', row['timestamp'])):
            raise ValueError('Malformed Arquivo index row')
    return rows


def validate_capture(capture):
    scope = capture['request_scope']
    if capture['source_kind'] not in KINDS or scope.get('profile') != PROFILE or scope.get('archive') != 'arquivo.pt':
        raise ValueError('Unsupported Arquivo capture profile')
    retrieved = timestamp(capture['retrieved_at'])
    if capture['source_published_at'] is not None:
        raise ValueError('Arquivo captures do not infer publication dates')
    if capture['source_kind'] == 'arquivo_index_v3':
        target = query_target(capture['source_url'], capture['provider'])
        if (scope != dict(profile=PROFILE, archive='arquivo.pt', target_url=target) or
                any(capture[k] is not None for k in ('archive_capture_at', 'archive_digest', 'replay_url'))):
            raise ValueError('Arquivo index scope differs')
    else:
        source_spec(capture['source_url'], capture['provider'])
        stamp = timestamp(capture['archive_capture_at']).astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')
        if (set(scope) != {'profile', 'archive', 'index_capture_id'} or not re.fullmatch(r'capture-[a-f0-9]{64}', scope['index_capture_id']) or
                timestamp(capture['archive_capture_at']) > retrieved or not re.fullmatch(r'[A-Z2-7]{32}', capture['archive_digest']) or
                capture['replay_url'] != replay(stamp, capture['source_url'])):
            raise ValueError('Arquivo replay witness scope differs')


def verify_index(capture, raw):
    from .historical_expansion import same_target
    rows = entries(raw)
    if any(not same_target(r['url'], capture['request_scope']['target_url'], capture['provider']) for r in rows):
        raise ValueError('Arquivo index escaped its exact URL scope')
    return rows


def verify_witness(capture, raw, context):
    witness = context.get(capture['request_scope']['index_capture_id'])
    if not witness or witness[0]['source_kind'] != 'arquivo_index_v3' or witness[0]['provider'] != capture['provider']:
        raise ValueError('Arquivo replay lacks its retained index')
    stamp = timestamp(capture['archive_capture_at']).astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')
    if (base64.b32encode(hashlib.sha1(raw).digest()).decode() != capture['archive_digest'] or not any(
            r['timestamp'] == stamp and r['url'] == capture['source_url'] and r.get('digest') == capture['archive_digest'] and
            str(r.get('status')) == '200' for r in verify_index(witness[0], witness[1]))):
        raise ValueError('Arquivo replay digest/date/URL witness differs')


def validate_check(row, context):
    keys = {'kind', 'id', 'capture_id', 'provider', 'profile', 'provenance', 'source_url', 'target_url', 'checked_at', 'state',
            'http_status', 'transport_exit_code', 'comparison_eligible', 'archive_capture_at', 'archive_digest', 'index_capture_id'}
    if set(row) != keys or row['capture_id'] is not None or row['profile'] != PROFILE or row['provenance'] != 'historical_discovery_v3' or row['comparison_eligible'] is not False:
        raise ValueError('Invalid Arquivo coverage check')
    timestamp(row['checked_at'])
    source_spec(row['target_url'], row['provider'])
    allowed = {'archive_index_empty', 'transport_failed', 'http_failed', 'redirect_denied', 'digest_mismatch', 'extractor_rejected', 'oversized_or_empty_body', 'invalid_transport'}
    if row['state'] not in allowed or row['transport_exit_code'] is not None:
        raise ValueError('Unsupported Arquivo check state')
    status = row['http_status']
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        raise ValueError('Invalid Arquivo HTTP status')
    if row['archive_capture_at'] is None:
        if row['archive_digest'] is not None or row['index_capture_id'] is not None or query_target(row['source_url'], row['provider']) != row['target_url']:
            raise ValueError('Arquivo lookup cannot invent a capture')
        if row['state'] == 'archive_index_empty' and status != 200:
            raise ValueError('Empty-index success needs HTTP 200')
    else:
        stamp = timestamp(row['archive_capture_at']).astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')
        witness = context.get(row['index_capture_id'])
        if (row['state'] == 'archive_index_empty' or row['source_url'] != replay(stamp, row['target_url']) or not witness or
                witness[0]['source_kind'] != 'arquivo_index_v3' or witness[0]['provider'] != row['provider'] or not any(
                r['timestamp'] == stamp and r['url'] == row['target_url'] and r.get('digest') == row['archive_digest'] and str(r.get('status')) == '200'
                for r in verify_index(witness[0], witness[1]))):
            raise ValueError('Arquivo failure lacks its exact index witness')
