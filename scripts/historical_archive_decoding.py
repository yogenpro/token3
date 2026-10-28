"""Bounded document decoding for derivative research; source bytes never change."""
import brotli
import re

from .historical_sources import MAX_BYTES, decoded


def document_text(raw):
    content = decoded(raw)
    try:
        return content.decode('utf-8-sig'), 'utf-8'
    except UnicodeError:
        if content.startswith((b'\xff\xfe', b'\xfe\xff')):
            return content.decode('utf-16'), 'utf-16-bom'
        declared = re.search(br'<meta\b[^>]*charset\s*=\s*["\']?([a-zA-Z0-9_-]+)', content[:32768], re.I)
        encodings = {b'windows-1252': 'cp1252', b'iso-8859-1': 'iso-8859-1', b'gb2312': 'gb2312', b'gb18030': 'gb18030'}
        if declared and declared[1].lower() in encodings:
            encoding = encodings[declared[1].lower()]
            return content.decode(encoding), 'html-declared-' + encoding
        decoder = brotli.Decompressor()
        try:
            result = decoder.process(content, output_buffer_limit=MAX_BYTES + 1)
        except brotli.error as exc:
            raise ValueError('Unsupported document encoding') from exc
        if len(result) > MAX_BYTES or not decoder.is_finished():
            raise ValueError('Incomplete or oversized Brotli document')
        return result.decode('utf-8-sig'), 'brotli'
