"""Best-effort verified Wayback references; never upload credentials/responses."""
import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


def _get(url):
    request = Request(url, headers={"User-Agent": "TokenTokenToken/0.1 (public pricing reference)", "Accept": "application/json, text/plain"})
    with urlopen(request, timeout=8) as response:
        if urlparse(response.geturl()).hostname not in ("archive.org", "web.archive.org"):
            raise ValueError("Archive request redirected outside Internet Archive")
        raw = response.read(8 * 1024 * 1024 + 1)
        if len(raw) > 8 * 1024 * 1024:
            raise ValueError("Archive response too large")
        return raw


def lookup_reference(result, observed_at):
    # Public-document references only. Authenticated APIs and assembled feeds
    # cannot be reproduced by an anonymous crawler; never send their bodies.
    if result.source_kind != "documentation":
        return dict(state="not_applicable", reason="API/feed responses are not public page captures")
    target = (result.source_urls or [result.source_url])[0]
    if urlparse(target).scheme != "https" or urlparse(target).query or urlparse(target).username:
        return dict(state="not_applicable", reason="Only credential-free public document URLs are queried")
    stamp = datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y%m%d%H%M%S")
    try:
        data = json.loads(_get("https://archive.org/wayback/available?" + urlencode(dict(url=target, timestamp=stamp))))
        closest = data.get("archived_snapshots", {}).get("closest", {})
        if not closest.get("available") or str(closest.get("status")) != "200":
            return dict(state="unavailable", target_url=target, checked_at=observed_at)
        capture = closest.get("timestamp", "")
        if not re.fullmatch(r"\d{14}", capture):
            raise ValueError("Invalid archive capture timestamp")
        captured_at = datetime.strptime(capture, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        replay = closest.get("url", "")
        parsed = urlparse(replay)
        if parsed.hostname != "web.archive.org" or not parsed.path.startswith("/web/" + capture + "/"):
            raise ValueError("Unexpected archive replay URL")
        expected_path = "/web/" + capture + "/" + target
        if parsed.path + ("?" + parsed.query if parsed.query else "") != expected_path:
            raise ValueError("Archive replay target does not match the source")
        raw_url = "https://web.archive.org/web/" + capture + "id_/" + target
        # Exact collector-body equivalence is stronger than proximity of dates.
        # A nearest capture with different prices/content is never 'verified'.
        same = hashlib.sha256(_get(raw_url)).hexdigest() == result.source_sha256
        return dict(state="verified" if same else "content_mismatch", target_url=target,
                    url="https://web.archive.org" + expected_path, capture_at=captured_at,
                    checked_at=observed_at, verification="exact_source_sha256" if same else None)
    except Exception as exc:
        return dict(state="unavailable", target_url=target, checked_at=observed_at,
                    reason="{}: {}".format(type(exc).__name__, exc)[:200])
