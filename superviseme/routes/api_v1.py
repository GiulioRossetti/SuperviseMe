"""
superviseme/routes/api_v1.py
-----------------------------
REST API v1 blueprint.

All endpoints are under ``/api/v1/`` and return JSON (or SSE for the
notification stream).  CSRF protection is explicitly exempted on these routes
because they use token-based authentication via the existing Flask-Login
session cookie, and the ``X-Requested-With: XMLHttpRequest`` header guards
against cross-site requests from third-party origins.

Registered in ``create_app()`` as::

    from superviseme.routes.api_v1 import api_v1 as api_v1_blueprint
    app.register_blueprint(api_v1_blueprint)

Endpoints
---------
Theses
    GET  /api/v1/theses                 — paginated list of public theses
    GET  /api/v1/theses/<id>            — single thesis detail

Users (authenticated)
    GET  /api/v1/users/me               — current user profile
    GET  /api/v1/users/<id>             — public user profile (supervisor/researcher)

Notifications (authenticated)
    GET  /api/v1/notifications          — paginated notification list
    POST /api/v1/notifications/<id>/read — mark one notification as read
    POST /api/v1/notifications/read-all  — mark all notifications as read
    GET  /api/v1/notifications/stream   — SSE stream (replaces JS polling)

Academic
    GET  /api/v1/academic/search        — combined CrossRef + OpenAlex search
    GET  /api/v1/academic/enrich        — enrich a thesis title with related works
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from functools import wraps
from typing import Generator

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    g,
    jsonify,
    request,
    stream_with_context,
)
from flask_login import current_user, login_required

logger = logging.getLogger(__name__)

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paginate_args():
    """Extract validated ``page`` / ``per_page`` from request args."""
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
    return page, per_page


def _thesis_dict(thesis) -> dict:
    """Serialise a Thesis model instance to a dict."""
    tags = [t.tag for t in (thesis.tags or [])]
    return {
        "id": thesis.id,
        "title": thesis.title,
        "description": thesis.description,
        "short_description": thesis.short_description,
        "topic": thesis.topic,
        "level": thesis.level,
        "is_public": thesis.is_public,
        "frozen": thesis.frozen,
        "created_at": thesis.created_at,
        "tags": tags,
        "publisher": {
            "id": thesis.publisher.id,
            "name": thesis.publisher.name,
            "surname": thesis.publisher.surname,
        } if thesis.publisher else None,
    }


def _notification_dict(notif) -> dict:
    """Serialise a Notification model instance to a dict."""
    return {
        "id": notif.id,
        "type": notif.notification_type,
        "title": notif.title,
        "message": notif.message,
        "action_url": notif.action_url,
        "is_read": notif.is_read,
        "created_at": notif.created_at,
        "thesis_id": notif.thesis_id,
        "actor": {
            "id": notif.actor.id,
            "name": notif.actor.name,
            "surname": notif.actor.surname,
        } if notif.actor else None,
    }


def _user_dict(user, include_private: bool = False) -> dict:
    """Serialise a User_mgmt model instance.

    *include_private* adds email and account metadata (only for /me).
    """
    base = {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "surname": user.surname,
        "user_type": user.user_type,
        "profile_pic": user.profile_pic,
        "orcid_id": user.orcid_id,
    }
    if include_private:
        base.update({
            "email": user.email,
            "is_enabled": user.is_enabled,
            "joined_on": user.joined_on,
            "last_activity": user.last_activity,
            "telegram_enabled": user.telegram_enabled,
        })
    return base


# ---------------------------------------------------------------------------
# Thesis endpoints
# ---------------------------------------------------------------------------

@api_v1.get("/theses")
def list_theses():
    """List public, non-frozen theses with optional keyword and level filters.

    Query params:
        q        — keyword search on title / description / topic
        level    — filter by level string
        page     — page number (default 1)
        per_page — results per page (default 20, max 100)
    """
    from superviseme.services.thesis_service import get_public_theses

    page, per_page = _paginate_args()
    keyword = request.args.get("q", "").strip() or None
    level = request.args.get("level", "").strip() or None

    pagination = get_public_theses(page=page, per_page=per_page, keyword=keyword, level=level)
    return jsonify({
        "theses": [_thesis_dict(t) for t in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


@api_v1.get("/theses/<int:thesis_id>")
def get_thesis(thesis_id: int):
    """Return a single thesis by ID.  Only public theses are exposed."""
    from superviseme.services.thesis_service import get_thesis_or_404

    thesis = get_thesis_or_404(thesis_id)
    if not thesis.is_public:
        abort(404)
    return jsonify(_thesis_dict(thesis))


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------

@api_v1.get("/users/me")
@login_required
def get_me():
    """Return the current authenticated user's profile."""
    return jsonify(_user_dict(current_user, include_private=True))


@api_v1.get("/users/<int:user_id>")
def get_user(user_id: int):
    """Return a public profile for a supervisor or researcher.

    Students and disabled accounts are not publicly exposed.
    """
    from superviseme.models import User_mgmt

    user = User_mgmt.query.get_or_404(user_id)
    if not user.is_enabled or user.user_type not in ("supervisor", "researcher"):
        abort(404)
    return jsonify(_user_dict(user, include_private=False))


# ---------------------------------------------------------------------------
# Notification endpoints
# ---------------------------------------------------------------------------

@api_v1.get("/notifications")
@login_required
def list_notifications():
    """Return paginated notifications for the current user.

    Query params:
        unread_only — 1 / true to return only unread
        page        — page number
        per_page    — results per page (max 100)
    """
    from superviseme.models import Notification

    page, per_page = _paginate_args()
    unread_only = request.args.get("unread_only", "").lower() in ("1", "true", "yes")

    q = Notification.query.filter_by(recipient_id=current_user.id)
    if unread_only:
        q = q.filter_by(is_read=False)
    q = q.order_by(Notification.created_at.desc())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    from superviseme.services.notification_service import get_unread_count
    return jsonify({
        "notifications": [_notification_dict(n) for n in pagination.items],
        "unread_count": get_unread_count(current_user.id),
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    })


@api_v1.post("/notifications/<int:notification_id>/read")
@login_required
def mark_notification_read(notification_id: int):
    """Mark a single notification as read."""
    from superviseme import db
    from superviseme.models import Notification
    from superviseme.services.notification_service import invalidate_unread_count

    notif = Notification.query.filter_by(
        id=notification_id, recipient_id=current_user.id
    ).first_or_404()
    if not notif.is_read:
        notif.is_read = True
        db.session.commit()
        invalidate_unread_count(current_user.id)
    return jsonify({"ok": True, "id": notification_id})


@api_v1.post("/notifications/read-all")
@login_required
def mark_all_notifications_read():
    """Mark all of the current user's notifications as read."""
    from superviseme.services.notification_service import mark_all_read

    updated = mark_all_read(current_user.id)
    return jsonify({"ok": True, "updated": updated})


# ---------------------------------------------------------------------------
# SSE notification stream
# ---------------------------------------------------------------------------
# A thread-safe fan-out registry: maps user_id → set of Queue objects.
# Each open SSE connection gets its own Queue; the notification service (or
# any code path) can push an event dict into every queue for a given user.
#
# Usage from other code:
#   from superviseme.routes.api_v1 import push_sse_event
#   push_sse_event(user_id=42, event={"type": "new_notification", "count": 3})

_sse_lock = threading.Lock()
_sse_queues: dict[int, set] = {}   # user_id → set[queue.Queue]


def push_sse_event(user_id: int, event: dict) -> None:
    """Push *event* (a JSON-serialisable dict) to all open SSE connections for *user_id*."""
    with _sse_lock:
        queues = _sse_queues.get(user_id, set())
        for q in queues:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass   # Slow client — drop the event rather than block


def _sse_format(data: dict, event: str | None = None, id: str | None = None) -> str:
    """Format a dict as a Server-Sent Event string."""
    lines = []
    if id is not None:
        lines.append(f"id: {id}")
    if event is not None:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")   # blank line terminator
    lines.append("")
    return "\n".join(lines)


@api_v1.get("/notifications/stream")
@login_required
def notification_stream():
    """SSE endpoint — push real-time notification events to the browser.

    The browser keeps a persistent HTTP connection and receives events as:

        event: notification
        data: {"type": "new_notification", "unread_count": 3, ...}

    A heartbeat ``event: ping`` is sent every 25 seconds to keep the
    connection alive through proxies that close idle connections.

    The client should reconnect automatically (the browser EventSource API
    does this natively).  Reconnection is handled via the ``Last-Event-ID``
    header on the client side.

    Example JS::

        const src = new EventSource("/api/v1/notifications/stream");
        src.addEventListener("notification", e => {
            const data = JSON.parse(e.data);
            document.querySelector("#badge").textContent = data.unread_count;
        });
    """
    user_id = current_user.id

    def generate() -> Generator[str, None, None]:
        q: queue.Queue = queue.Queue(maxsize=50)

        # Register this connection
        with _sse_lock:
            _sse_queues.setdefault(user_id, set()).add(q)

        try:
            # Send initial unread count so the client is up-to-date immediately
            from superviseme.services.notification_service import get_unread_count
            yield _sse_format(
                {"type": "connected", "unread_count": get_unread_count(user_id)},
                event="notification",
                id="0",
            )

            last_ping = time.monotonic()
            while True:
                # Block for up to 5 seconds waiting for an event
                try:
                    event = q.get(timeout=5)
                    yield _sse_format(event, event="notification")
                except queue.Empty:
                    pass

                # Heartbeat every 25 s
                if time.monotonic() - last_ping >= 25:
                    yield _sse_format({"type": "ping"}, event="ping")
                    last_ping = time.monotonic()

        except GeneratorExit:
            pass
        finally:
            # Clean up on client disconnect
            with _sse_lock:
                queues = _sse_queues.get(user_id, set())
                queues.discard(q)
                if not queues:
                    _sse_queues.pop(user_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable Nginx buffering for SSE
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Academic search endpoints
# ---------------------------------------------------------------------------

@api_v1.get("/academic/search")
def academic_search():
    """Search CrossRef and/or OpenAlex for related works.

    Query params:
        q        — search query (required)
        source   — "crossref", "openalex", or "both" (default "both")
        per_page — results per source (default 5, max 20)
        page     — CrossRef offset page (default 1)
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Missing required parameter: q"}), 400

    source = request.args.get("source", "both").lower()
    per_page = min(20, max(1, request.args.get("per_page", 5, type=int)))
    page = max(1, request.args.get("page", 1, type=int))

    from superviseme.utils.academic_apis import search_crossref, search_openalex

    result: dict = {"query": query}

    if source in ("crossref", "both"):
        result["crossref"] = search_crossref(query, rows=per_page, offset=(page - 1) * per_page)

    if source in ("openalex", "both"):
        result["openalex"] = search_openalex(query, per_page=per_page, page=page)

    return jsonify(result)


@api_v1.get("/academic/enrich")
def academic_enrich():
    """Enrich a thesis title with related published works.

    Query params:
        title    — thesis title (required)
        max      — max results per source (default 3, max 10)
    """
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({"error": "Missing required parameter: title"}), 400

    max_results = min(10, max(1, request.args.get("max", 3, type=int)))

    from superviseme.utils.academic_apis import enrich_thesis

    return jsonify(enrich_thesis(title, max_results=max_results))
