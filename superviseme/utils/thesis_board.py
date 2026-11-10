"""View-models for the thesis boards (admin, supervisor and researcher "theses" pages)."""
from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from superviseme import db
from superviseme.models import Thesis, Thesis_Interest, Thesis_Status, Thesis_Supervisor, Todo


def build_thesis_cards(theses):
    """Enrich each thesis with the data shown on its card; returns (active, archived) lists.

    Everything is loaded with a constant number of queries (grouped counts and eager loads),
    independent of how many theses are shown.
    """
    unique, seen = [], set()
    for t in theses:
        if t and t.id not in seen:
            seen.add(t.id)
            unique.append(t)
    if not unique:
        return [], []
    ids = [t.id for t in unique]

    # Warm the identity map so t.author / t.tags / t.images / t.links do not trigger one query each.
    Thesis.query.options(
        joinedload(Thesis.author), selectinload(Thesis.tags), selectinload(Thesis.images), selectinload(Thesis.links),
    ).filter(Thesis.id.in_(ids)).all()

    latest_status = {}
    for s in Thesis_Status.query.filter(Thesis_Status.thesis_id.in_(ids)).order_by(Thesis_Status.updated_at.asc(), Thesis_Status.id.asc()):
        latest_status[s.thesis_id] = s

    todo_total, todo_done = defaultdict(int), defaultdict(int)
    for thesis_id, status, n in (
        db.session.query(Todo.thesis_id, Todo.status, func.count(Todo.id)).filter(Todo.thesis_id.in_(ids)).group_by(Todo.thesis_id, Todo.status)
    ):
        todo_total[thesis_id] += n
        if status == "completed":
            todo_done[thesis_id] += n

    pending = dict(
        db.session.query(Thesis_Interest.thesis_id, func.count(Thesis_Interest.id))
        .filter(Thesis_Interest.thesis_id.in_(ids), Thesis_Interest.status == "pending")
        .group_by(Thesis_Interest.thesis_id).all()
    )

    supervisors = defaultdict(list)
    for row in Thesis_Supervisor.query.options(joinedload(Thesis_Supervisor.supervisor)).filter(Thesis_Supervisor.thesis_id.in_(ids)):
        if row.supervisor:
            supervisors[row.thesis_id].append(row.supervisor)

    active, archived = [], []
    for t in unique:
        status = latest_status.get(t.id)
        total = todo_total[t.id] if t.author_id else 0
        done = todo_done[t.id] if total else 0
        card = {
            "thesis": t,
            "student": t.author,
            "state": "frozen" if t.frozen else ("assigned" if t.author_id else "open"),
            "status": status.status if status else None,
            "todos_total": total,
            "todos_done": done,
            "progress": int(round(100 * done / total)) if total else None,
            "pending_interests": pending.get(t.id, 0) if not t.author_id else 0,
            "keywords": [tag.tag for tag in t.tags],
            "images": len(t.images),
            "links": len(t.links),
            "supervisors": supervisors.get(t.id, []),
        }
        (archived if t.frozen else active).append(card)
    key = lambda c: -(c["thesis"].created_at or 0)
    return sorted(active, key=key), sorted(archived, key=key)
