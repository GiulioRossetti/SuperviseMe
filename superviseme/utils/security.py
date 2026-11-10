"""Security helpers: login throttling, password policy, HTTP security headers, API CSRF guard.

The login throttle keeps its counters in process memory. With several gunicorn workers each
worker counts separately, so the effective limit is ``limit * workers``; put a shared limiter
(nginx ``limit_req`` or Redis) in front of the app when strict global limits are required.
"""
import re
import threading
import time
from urllib.parse import urlparse

from flask import current_app, jsonify, request
from flask_babel import gettext as _

PASSWORD_MIN_LENGTH = 8

_fallback_state = {"lock": threading.Lock(), "fail": {}}


def _state():
    """Per-application counters (so every app instance, e.g. in tests, starts clean)."""
    try:
        return current_app.extensions.setdefault(
            "sm_login_throttle", {"lock": threading.Lock(), "fail": {}}
        )
    except RuntimeError:
        return _fallback_state


def _cfg(name, default):
    try:
        return current_app.config.get(name, default)
    except RuntimeError:
        return default


def _prune(fail, key, now, window):
    hits = [t for t in fail.get(key, []) if now - t < window]
    if hits:
        fail[key] = hits
    else:
        fail.pop(key, None)
    return hits


def _keys(email, ip):
    return (f"acct:{(email or '').strip().lower()}|{ip or '-'}", f"ip:{ip or '-'}")


def reset_throttle():
    st = _state()
    with st["lock"]:
        st["fail"].clear()


def throttle_status(email, ip):
    """Return seconds to wait if the (email, ip) pair or the ip is locked out, else 0."""
    if not _cfg("LOGIN_THROTTLE_ENABLED", True):
        return 0
    window = int(_cfg("LOGIN_THROTTLE_WINDOW", 900))
    limits = (int(_cfg("LOGIN_THROTTLE_MAX_ACCOUNT", 5)), int(_cfg("LOGIN_THROTTLE_MAX_IP", 30)))
    now = time.time()
    wait = 0
    st = _state()
    with st["lock"]:
        for key, limit in zip(_keys(email, ip), limits):
            hits = _prune(st["fail"], key, now, window)
            if len(hits) >= limit:
                wait = max(wait, int(window - (now - hits[0])) + 1)
    return wait


def record_login_failure(email, ip):
    now = time.time()
    st = _state()
    with st["lock"]:
        for key in _keys(email, ip):
            st["fail"].setdefault(key, []).append(now)


def record_login_success(email, ip):
    st = _state()
    with st["lock"]:
        st["fail"].pop(_keys(email, ip)[0], None)


def validate_password(password):
    """Return an error message when the password breaks the policy, else None."""
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return _("The password must be at least %(n)d characters long.", n=PASSWORD_MIN_LENGTH)
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return _("The password must contain at least one letter and one digit.")
    return None


def build_csp():
    """Content-Security-Policy string (pragmatic policy).

    'unsafe-inline' stays for scripts/styles because templates still use inline
    handlers and <script> blocks; everything else is restricted to this origin
    plus the few CDNs the UI loads fonts/styles from. CSP_EXTRA_SOURCES (space
    separated) is appended to script/style/font/img/connect, CSP_REPORT_URI
    adds a report endpoint.
    """
    extra = " ".join((_cfg("CSP_EXTRA_SOURCES", "") or "").split())
    def src(base):
        return (base + " " + extra).strip()
    directives = [
        "default-src 'self'",
        src("script-src 'self' 'unsafe-inline'"),
        src("style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com"),
        src("font-src 'self' data: https://fonts.gstatic.com"),
        src("img-src 'self' data: blob: https:"),
        src("connect-src 'self'"),
        "object-src 'none'",
        "base-uri 'self'",
        "frame-ancestors 'self'",
    ]
    report = _cfg("CSP_REPORT_URI", "")
    if report:
        directives.append(f"report-uri {report}")
    return "; ".join(directives)


def apply_security_headers(response):
    h = response.headers
    mode = str(_cfg("CSP_MODE", "enforce")).lower()
    if mode in ("enforce", "report-only"):
        name = "Content-Security-Policy" + ("-Report-Only" if mode == "report-only" else "")
        h.setdefault(name, build_csp())
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "SAMEORIGIN")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if _cfg("SESSION_COOKIE_SECURE", False):
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def api_csrf_guard():
    """before_request for the CSRF-exempt JSON API: state-changing calls must be same-origin XHR."""
    if not request.path.startswith("/api/v1/") or request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    ok = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if ok and origin:
        ok = urlparse(origin).netloc == request.host
    if not ok:
        return jsonify({"status": "error", "message": "Cross-site or non-XHR request rejected."}), 403
    return None
