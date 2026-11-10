"""Data builders for the role dashboards (kept out of the routes to share them)."""
import time
from datetime import datetime

from sqlalchemy.orm import joinedload

from superviseme.models import (
    Resource,
    Thesis,
    Thesis_Milestone,
    Thesis_Status,
    Thesis_Supervisor,
    Thesis_Update,
    Todo,
    User_mgmt,
)
from superviseme.utils.activity_tracker import get_inactive_students
from superviseme.utils.thesis_board import build_thesis_cards


def greeting_key():
    hour = datetime.now().hour
    return "morning" if hour < 12 else ("afternoon" if hour < 18 else "evening")


def _days_since(ts, now):
    return None if not ts else max(0, (now - ts) // 86400)


def _recent_updates(thesis_ids, limit=6):
    if not thesis_ids:
        return []
    rows = (
        Thesis_Update.query.filter(Thesis_Update.thesis_id.in_(thesis_ids))
        .order_by(Thesis_Update.created_at.desc())
        .limit(limit)
        .all()
    )
    authors = {u.id: u for u in User_mgmt.query.filter(User_mgmt.id.in_({r.author_id for r in rows})).all()} if rows else {}
    titles = {t.id: t.title for t in Thesis.query.filter(Thesis.id.in_({r.thesis_id for r in rows})).all()} if rows else {}
    return [
        {"upd": r, "author": authors.get(r.author_id), "thesis_title": titles.get(r.thesis_id, "")}
        for r in rows
    ]


def supervisor_overview(user):
    """Everything the supervisor dashboards need, in one dict."""
    now = int(time.time())
    links = (
        Thesis_Supervisor.query.filter_by(supervisor_id=user.id)
        .options(joinedload(Thesis_Supervisor.thesis))
        .all()
    )
    theses = [ts.thesis for ts in links if ts.thesis]
    active, archived = build_thesis_cards(theses)
    assigned = [c for c in active if c["state"] == "assigned"]
    open_cards = [c for c in active if c["state"] == "open"]
    for c in assigned:
        c["days_inactive"] = _days_since(c["student"].last_activity, now)
    ids = [t.id for t in theses]

    todos = []
    if ids:
        todos = (
            Todo.query.filter(Todo.thesis_id.in_(ids))
            .order_by(Todo.status.asc(), Todo.priority.desc(), Todo.created_at.desc())
            .all()
        )
    pending = [t for t in todos if t.status == "pending"]
    overdue = [t for t in pending if t.due_date and t.due_date < now]
    students_by_thesis = {c["thesis"].id: c["student"] for c in assigned}

    inactive = [
        d for d in get_inactive_students(user.id)
        if d["is_inactive"] and not d["thesis"].frozen
    ]
    pipeline = {}
    for c in active:
        key = c["status"] or ("open" if c["state"] == "open" else "no-status")
        pipeline[key] = pipeline.get(key, 0) + 1

    upcoming = (
        Thesis_Milestone.query.filter(Thesis_Milestone.thesis_id.in_(ids), Thesis_Milestone.status == "pending")
        .order_by(Thesis_Milestone.due_date.asc()).limit(6).all()
        if ids else []
    )
    titles = {t.id: t.title for t in theses}
    return {
        "milestones": [{"m": m, "thesis_title": titles.get(m.thesis_id, "")} for m in upcoming],
        "stats": {
            "students": len(assigned),
            "theses": len(active),
            "open": len(open_cards),
            "pending_interests": sum(c["pending_interests"] for c in open_cards),
            "open_todos": len(pending),
            "overdue": len(overdue),
        },
        "assigned": assigned,
        "open_cards": open_cards,
        "archived": archived,
        "todos": todos,
        "overdue": overdue,
        "inactive": inactive,
        "pipeline": sorted(pipeline.items(), key=lambda kv: -kv[1]),
        "recent": _recent_updates(ids),
        "students_by_thesis": students_by_thesis,
        "assignable": [{"thesis": c["thesis"], "student": c["student"]} for c in assigned],
        "now": now,
        "greeting": greeting_key(),
    }


def student_overview(user, thesis, todos):
    """Progress/status data for the student dashboard."""
    now = int(time.time())
    if not thesis:
        return {"greeting": greeting_key(), "supervisors": [], "now": now}
    status = (
        Thesis_Status.query.filter_by(thesis_id=thesis.id)
        .order_by(Thesis_Status.updated_at.desc())
        .first()
    )
    supervisors = [
        ts.supervisor
        for ts in Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()
        if ts.supervisor
    ]
    pending = [t for t in todos if t.status == "pending"]
    done = [t for t in todos if t.status == "completed"]
    countable = len(pending) + len(done)
    pending_sorted = sorted(pending, key=lambda t: (t.due_date is None, t.due_date or 0))
    return {
        "greeting": greeting_key(),
        "now": now,
        "status": status.status if status else None,
        "supervisors": supervisors,
        "pending": pending_sorted,
        "done_count": len(done),
        "overdue": len([t for t in pending if t.due_date and t.due_date < now]),
        "progress": int(round(100 * len(done) / countable)) if countable else None,
        "keywords": [t.tag for t in thesis.tags],
        "milestones": [m for m in thesis.milestones if m.status == "pending"][:4],
        "milestones_done": len([m for m in thesis.milestones if m.status == "done"]),
        "milestones_total": len(thesis.milestones),
        "recent": _recent_updates([thesis.id], limit=5),
        "resources": Resource.query.filter_by(thesis_id=thesis.id).count(),
    }
