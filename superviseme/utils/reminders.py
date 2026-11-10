"""Automatic reminders (tasks, milestones, inactive students, meetings).

``run_reminders`` is idempotent: every (user, kind, ref, bucket) is sent at most once,
tracked in ``reminder_log``. It is scheduled daily and can be triggered by hand.
"""
import logging
import time
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from superviseme import db
from superviseme.models import (
    ReminderLog,
    Thesis,
    Thesis_Checklist_Item,
    Thesis_Milestone,
    Thesis_Supervisor,
    Todo,
    User_mgmt,
)

logger = logging.getLogger(__name__)
DAY = 86400


def _once(user_id, kind, ref_id, bucket):
    """Reserve the reminder slot; False if it was already used."""
    try:
        with db.session.begin_nested():
            db.session.add(ReminderLog(user_id=user_id, kind=kind, ref_id=ref_id, bucket=bucket, sent_at=int(time.time())))
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False


def _notify(recipient_id, kind, ref_id, bucket, title, message, thesis_id=None, url=None):
    from superviseme.utils.notifications import build_role_aware_url, create_notification

    if not _once(recipient_id, kind, ref_id, bucket):
        return 0
    action = build_role_aware_url(recipient_id, url, thesis_id) if url else None
    create_notification(recipient_id, recipient_id, "deadline_reminder", title, message, thesis_id=thesis_id, action_url=action)
    return 1


def _thesis_people(thesis):
    ids = [ts.supervisor_id for ts in Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()]
    if thesis.author_id:
        ids.append(thesis.author_id)
    return ids


def run_reminders(now=None, inactive_days=14):
    now = int(now or time.time())
    sent = {"todo": 0, "milestone": 0, "checklist": 0, "inactive": 0, "meeting": 0}

    # --- tasks: due within 48h, or overdue ------------------------------------------------
    for todo in Todo.query.filter(Todo.status == "pending", Todo.due_date.isnot(None)).all():
        thesis = db.session.get(Thesis, todo.thesis_id)
        if not thesis or thesis.frozen:
            continue
        if todo.due_date < now:
            bucket, label = "late", "is overdue"
        elif todo.due_date - now <= 2 * DAY:
            bucket, label = "soon", "is due soon"
        else:
            continue
        who = todo.assigned_to_id or todo.author_id
        due = datetime.utcfromtimestamp(todo.due_date).strftime("%d %b %Y")
        sent["todo"] += _notify(who, "todo", todo.id, bucket, f"Task {label}: {todo.title}", f"Due {due} — thesis \"{thesis.title}\".", thesis.id, None)

    # --- milestones: 7 days, 1 day, overdue -----------------------------------------------
    for m in Thesis_Milestone.query.filter_by(status="pending").all():
        thesis = db.session.get(Thesis, m.thesis_id)
        if not thesis or thesis.frozen:
            continue
        left = m.due_date - now
        if left < 0:
            bucket, label = "late", "is overdue"
        elif left <= DAY:
            bucket, label = "day", "is due tomorrow"
        elif left <= 7 * DAY:
            bucket, label = "week", "is due within a week"
        else:
            continue
        due = datetime.utcfromtimestamp(m.due_date).strftime("%d %b %Y")
        for uid in _thesis_people(thesis):
            sent["milestone"] += _notify(uid, "milestone", m.id, bucket, f"Milestone {label}: {m.title}", f"Due {due} — thesis \"{thesis.title}\".", thesis.id)

    # --- graduation checklist: same buckets as milestones --------------------------------
    for item in Thesis_Checklist_Item.query.filter(Thesis_Checklist_Item.status == "pending",
                                                   Thesis_Checklist_Item.due_date.isnot(None)).all():
        thesis = db.session.get(Thesis, item.thesis_id)
        if not thesis or thesis.frozen:
            continue
        left = item.due_date - now
        if left < 0:
            bucket, label = "late", "is overdue"
        elif left <= DAY:
            bucket, label = "day", "is due tomorrow"
        elif left <= 7 * DAY:
            bucket, label = "week", "is due within a week"
        else:
            continue
        due = datetime.utcfromtimestamp(item.due_date).strftime("%d %b %Y")
        for uid in _thesis_people(thesis):
            sent["checklist"] += _notify(uid, "checklist", item.id, bucket, f"Graduation step {label}: {item.title}", f"Due {due} — thesis \"{thesis.title}\".", thesis.id)

    # --- inactive students: tell supervisors once per ISO week ---------------------------
    iso = datetime.utcfromtimestamp(now).isocalendar()
    week = f"{iso[0]}-W{iso[1]:02d}"
    cutoff = now - inactive_days * DAY
    for thesis in Thesis.query.filter(Thesis.author_id.isnot(None)).all():
        if thesis.frozen:
            continue
        student = db.session.get(User_mgmt, thesis.author_id)
        if not student or (student.last_activity and student.last_activity >= cutoff):
            continue
        days = None if not student.last_activity else (now - student.last_activity) // DAY
        text = "has never logged in" if days is None else f"has been inactive for {days} days"
        for ts in Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all():
            sent["inactive"] += _notify(ts.supervisor_id, "inactive", student.id, week, f"{student.name} {student.surname} {text}", f"Thesis \"{thesis.title}\".", thesis.id)

    # --- meetings (defined by the meetings feature when available) -----------------------
    try:
        from superviseme.utils.meetings import meeting_reminders
        sent["meeting"] = meeting_reminders(now, _notify)
    except ImportError:
        pass

    logger.info("reminders sent: %s", sent)
    return sent
