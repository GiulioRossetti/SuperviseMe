"""Shared helpers for the workflow features (milestones, meetings, documents, ...)."""
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import abort, request, url_for

from superviseme.models import Thesis, Thesis_Supervisor


def thesis_role(user, thesis):
    """'admin' | 'supervisor' | 'student' | None for ``user`` on ``thesis``."""
    if not getattr(user, "is_authenticated", False):
        return None
    if user.user_type == "admin":
        return "admin"
    if thesis.author_id == user.id:
        return "student"
    if Thesis_Supervisor.query.filter_by(thesis_id=thesis.id, supervisor_id=user.id).first():
        return "supervisor"
    return None


def load_thesis_or_403(user, thesis_id, roles=("admin", "supervisor", "student")):
    thesis = Thesis.query.get_or_404(thesis_id)
    role = thesis_role(user, thesis)
    if role not in roles:
        abort(403)
    return thesis, role


def safe_next(default_endpoint="public.public_thesis_dashboard", **values):
    """Return the ``next`` form/query value only if it is a same-site relative path."""
    nxt = request.values.get("next") or ""
    parsed = urlparse(nxt)
    if nxt.startswith("/") and not nxt.startswith("//") and not parsed.netloc and "\\" not in nxt:
        return nxt
    return url_for(default_endpoint, **values)


def parse_date(value):
    """'YYYY-MM-DD' (or 'YYYY-MM-DDTHH:MM') -> unix timestamp (UTC) or None."""
    value = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M"):
        try:
            return int(datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    return None


def now():
    return int(time.time())
