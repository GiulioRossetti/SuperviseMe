"""Privacy / GDPR helpers: profile-view log, personal data export, erasure, retention policy."""
import os
import secrets
import time

from flask import current_app
from werkzeug.security import generate_password_hash

from superviseme import db
from superviseme.models import (
    Calendar_Feed,
    Document_Comment,
    MeetingNote,
    Notification,
    Profile_View,
    ReminderLog,
    Thesis,
    Thesis_Document_Version,
    Thesis_Interest,
    Thesis_Supervisor,
    Thesis_Update,
    Todo,
    User_mgmt,
)
from superviseme.utils.uploads import delete_file

MONTH = 30 * 86400
VIEW_DEDUP_SECONDS = 3600
SENSITIVE_COLUMNS = {"password", "orcid_access_token"}


def retention_months():
    try:
        return max(1, int(current_app.config.get("RETENTION_MONTHS") or os.environ.get("RETENTION_MONTHS") or 24))
    except (TypeError, ValueError):
        return 24


def log_profile_view(viewer, target):
    """Record that ``viewer`` opened a student's profile (once per hour per viewer)."""
    try:
        if not viewer or not target or viewer.id == target.id or target.user_type != "student":
            return
        now = int(time.time())
        recent = Profile_View.query.filter(Profile_View.viewer_id == viewer.id, Profile_View.target_id == target.id,
                                           Profile_View.viewed_at > now - VIEW_DEDUP_SECONDS).first()
        if not recent:
            db.session.add(Profile_View(viewer_id=viewer.id, target_id=target.id, viewed_at=now))
            db.session.commit()
    except Exception:  # logging must never break the page
        db.session.rollback()


def _row(obj, exclude=()):
    out = {}
    for col in obj.__table__.columns:
        if col.name in SENSITIVE_COLUMNS or col.name in exclude:
            continue
        out[col.name] = getattr(obj, col.name)
    return out


def export_user_data(user):
    """Everything the platform stores about ``user`` as plain JSON-serialisable data."""
    uid = user.id
    ids = {t.id for t in Thesis.query.filter((Thesis.author_id == uid) | (Thesis.publisher_id == uid))}
    ids |= {r.thesis_id for r in Thesis_Supervisor.query.filter_by(supervisor_id=uid)}
    version_ids = [v.id for v in Thesis_Document_Version.query.filter_by(uploaded_by=uid)]
    return {
        "exported_at": int(time.time()),
        "profile": _row(user),
        "theses": [_row(t) for t in Thesis.query.filter(Thesis.id.in_(ids))] if ids else [],
        "supervision": [_row(r) for r in Thesis_Supervisor.query.filter_by(supervisor_id=uid)],
        "updates": [_row(r) for r in Thesis_Update.query.filter_by(author_id=uid)],
        "tasks": [_row(r) for r in Todo.query.filter((Todo.author_id == uid) | (Todo.assigned_to_id == uid))],
        "meeting_notes": [_row(r) for r in MeetingNote.query.filter_by(author_id=uid)],
        "document_comments": [_row(r) for r in Document_Comment.query.filter_by(author_id=uid)],
        "uploaded_document_versions": [_row(r, exclude=("filename",)) for r in Thesis_Document_Version.query.filter(Thesis_Document_Version.id.in_(version_ids))] if version_ids else [],
        "thesis_interests": [_row(r) for r in Thesis_Interest.query.filter_by(student_id=uid)],
        "notifications": [_row(r) for r in Notification.query.filter_by(recipient_id=uid).order_by(Notification.created_at.desc()).limit(1000)],
        "profile_views_received": [_row(r) for r in Profile_View.query.filter_by(target_id=uid)],
        # the secret feed address itself is deliberately not exported
        "calendar_feed": [{"connected_since": r.created_at, "last_sync": r.fetched_at} for r in Calendar_Feed.query.filter_by(user_id=uid)],
        "profile_views_made": [_row(r) for r in Profile_View.query.filter_by(viewer_id=uid)],
    }


def erasure_blockers(user):
    """Reasons why a user cannot be erased right now (empty list = allowed)."""
    reasons = []
    if user.user_type == "admin":
        reasons.append("Administrator accounts must be removed by another administrator.")
    if user.user_type in ("supervisor", "researcher"):
        active = Thesis.query.join(Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id).filter(
            Thesis_Supervisor.supervisor_id == user.id, Thesis.author_id.isnot(None), Thesis.frozen.isnot(True)).count()
        if active:
            reasons.append("You still supervise active theses: hand them over or archive them first.")
    return reasons


def anonymize_user(user):
    """Erase personal data of ``user`` while keeping the academic records they contributed to."""
    uid = user.id
    delete_file(user.profile_pic) if user.profile_pic else None
    user.username = f"deleted-{uid}"
    user.name, user.surname = "Deleted", "user"
    user.email = f"deleted-{uid}@invalid.local"
    user.password = generate_password_hash(secrets.token_urlsafe(32))
    user.is_enabled = False
    for col in ("cdl", "gender", "nationality", "google_id", "orcid_id", "orcid_access_token", "profile_pic", "office_location",
                "phone", "contact_email", "telegram_user_id", "telegram_notification_types", "last_activity_location"):
        if hasattr(user, col):
            setattr(user, col, None)
    user.telegram_enabled = False
    user.agenda_token = None
    user.email_notifications = False
    user.weekly_digest = False
    Calendar_Feed.query.filter_by(user_id=uid).delete()
    Notification.query.filter_by(recipient_id=uid).delete()
    Profile_View.query.filter((Profile_View.viewer_id == uid) | (Profile_View.target_id == uid)).delete()
    ReminderLog.query.filter_by(user_id=uid).delete()
    db.session.commit()


def purge_expired(now=None):
    """Apply the retention policy: drop old notifications, reminder log entries and profile views."""
    cutoff = int(now or time.time()) - retention_months() * MONTH
    counts = {
        "notifications": Notification.query.filter(Notification.created_at < cutoff).delete(),
        "reminders": ReminderLog.query.filter(ReminderLog.sent_at < cutoff).delete(),
        "profile_views": Profile_View.query.filter(Profile_View.viewed_at < cutoff).delete(),
    }
    db.session.commit()
    return counts
