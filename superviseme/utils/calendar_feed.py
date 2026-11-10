"""Read-only external calendars (iCal feed URLs) so the agenda can show a supervisor's busy time.

Only free/busy information is derived from the feed: titles, attendees and other event details are
never stored. The feed address is a secret (anyone with it can read the calendar) and is stored
encrypted. Fetching is hardened against server-side request forgery: https only, public addresses
only (unless ``CALENDAR_FEED_ALLOW_PRIVATE`` is set), manual and validated redirects, size and time limits.
"""
import ipaddress
import json
import socket
import time
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, urlparse

from flask import current_app

from superviseme import db
from superviseme.models import Calendar_Feed
from superviseme.utils.crypto import decrypt_token, encrypt_token

REFRESH_SECONDS = 15 * 60
RETRY_SECONDS = 5 * 60
HORIZON_DAYS = 90
MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 3
MAX_URL_LEN = 1000


class FeedError(Exception):
    """Raised with a short, user-presentable message."""


def normalize_url(raw):
    url = (raw or "").strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    if not url or len(url) > MAX_URL_LEN:
        raise FeedError("Enter the calendar's private iCal address.")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise FeedError("Only https:// (or webcal://) addresses are accepted.")
    if parsed.username or parsed.password:
        raise FeedError("Addresses with embedded credentials are not supported.")
    return url


def _allow_private():
    return bool(current_app.config.get("CALENDAR_FEED_ALLOW_PRIVATE"))


def _assert_public_host(host, port):
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise FeedError("The address could not be resolved.")
    if _allow_private():
        return
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise FeedError("The address points to a private network and cannot be used.")


def fetch_ics(url):
    import requests

    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        parsed = urlparse(current)
        if parsed.scheme != "https" or not parsed.hostname:
            raise FeedError("Only https:// addresses are accepted.")
        _assert_public_host(parsed.hostname, parsed.port or 443)
        try:
            resp = requests.get(current, timeout=(5, 10), allow_redirects=False, stream=True,
                                headers={"User-Agent": "SuperviseMe-calendar-sync", "Accept": "text/calendar, */*"})
        except requests.RequestException:
            raise FeedError("The calendar could not be downloaded.")
        try:
            if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                current = urljoin(current, resp.headers.get("Location", ""))
                continue
            if resp.status_code != 200:
                raise FeedError(f"The calendar server answered with error {resp.status_code}.")
            body = b""
            for chunk in resp.iter_content(64 * 1024):
                body += chunk
                if len(body) > MAX_BYTES:
                    raise FeedError("The calendar is too large.")
            return body.decode("utf-8", errors="replace")
        finally:
            resp.close()
    raise FeedError("Too many redirects.")


def _ts(value):
    """date/datetime from an iCal property -> unix timestamp (all-day: local midnight)."""
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, date):
        return int(datetime(value.year, value.month, value.day).timestamp())
    return None


def parse_busy(text, start_ts, end_ts):
    """Merged busy intervals [[start, end], ...] inside [start_ts, end_ts] from an iCal document."""
    try:
        import icalendar
        import recurring_ical_events
    except ImportError:
        raise FeedError("Calendar support is not installed on this server (icalendar, recurring-ical-events).")
    try:
        cal = icalendar.Calendar.from_ical(text)
        events = recurring_ical_events.of(cal).between(datetime.fromtimestamp(start_ts), datetime.fromtimestamp(end_ts))
    except Exception:
        raise FeedError("The address does not contain a valid iCal calendar.")
    spans = []
    for ev in events:
        if str(ev.get("STATUS", "")).upper() == "CANCELLED" or str(ev.get("TRANSP", "")).upper() == "TRANSPARENT":
            continue
        try:
            s, e = _ts(ev.start), _ts(ev.end)
        except Exception:
            continue
        if s is None:
            continue
        if e is None or e <= s:
            e = s + 30 * 60
        if e > start_ts and s < end_ts:
            spans.append([max(s, start_ts), min(e, end_ts)])
    return merge(spans)


def merge(spans):
    out = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def _window(now=None):
    now = int(now or time.time())
    return now - 86400, now + HORIZON_DAYS * 86400


def connect(user, raw_url):
    """Validate, download once, and store the feed (encrypted). Raises FeedError."""
    url = normalize_url(raw_url)
    start, end = _window()
    busy = parse_busy(fetch_ics(url), start, end)
    now = int(time.time())
    feed = Calendar_Feed.query.filter_by(user_id=user.id).first()
    if not feed:
        feed = Calendar_Feed(user_id=user.id, created_at=now, url_enc="")
        db.session.add(feed)
    feed.url_enc = encrypt_token(url)
    feed.busy_json, feed.fetched_at, feed.last_attempt_at, feed.last_error = json.dumps(busy), now, now, None
    db.session.commit()
    return feed


def disconnect(user):
    Calendar_Feed.query.filter_by(user_id=user.id).delete()
    db.session.commit()


def refresh(feed, force=False):
    """Re-download the feed when the cache is stale. Failures keep the previous busy data."""
    now = int(time.time())
    if not force:
        if feed.fetched_at and now - feed.fetched_at < REFRESH_SECONDS:
            return feed
        if feed.last_attempt_at and now - feed.last_attempt_at < RETRY_SECONDS and feed.last_error:
            return feed
    feed.last_attempt_at = now
    try:
        start, end = _window(now)
        busy = parse_busy(fetch_ics(normalize_url(decrypt_token(feed.url_enc))), start, end)
        feed.busy_json, feed.fetched_at, feed.last_error = json.dumps(busy), now, None
    except FeedError as exc:
        feed.last_error = str(exc)[:200]
    except Exception:
        feed.last_error = "Unexpected error while reading the calendar."
    db.session.commit()
    return feed


def busy_for(user_id, start_ts, end_ts, force=False):
    """Busy intervals of ``user_id`` clipped to [start_ts, end_ts]; [] if no calendar is connected."""
    feed = Calendar_Feed.query.filter_by(user_id=user_id).first()
    if not feed:
        return []
    refresh(feed, force=force)
    try:
        spans = json.loads(feed.busy_json or "[]")
    except ValueError:
        return []
    return [[max(s, start_ts), min(e, end_ts)] for s, e in spans if e > start_ts and s < end_ts]


def conflicts(user_id, start_ts, end_ts):
    return bool(busy_for(user_id, start_ts, end_ts))


def status(user_id):
    feed = Calendar_Feed.query.filter_by(user_id=user_id).first()
    if not feed:
        return None
    return {"fetched_at": feed.fetched_at, "error": feed.last_error}
