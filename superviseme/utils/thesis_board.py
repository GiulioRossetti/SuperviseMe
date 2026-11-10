"""View-models for the thesis boards (admin, supervisor and researcher "theses" pages)."""
from collections import defaultdict

from datetime import datetime

from flask import jsonify, render_template
from sqlalchemy import case, exists, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from superviseme import db
from superviseme.models import Thesis, Thesis_Interest, Thesis_Status, Thesis_Supervisor, Thesis_Tag, Todo, User_mgmt


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


# --- Server-side filtering / pagination ---------------------------------------------------------

def _like(term):
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _latest_status():
    """Correlated scalar subquery: the current status label of Thesis."""
    return (
        select(Thesis_Status.status).where(Thesis_Status.thesis_id == Thesis.id)
        .order_by(Thesis_Status.updated_at.desc(), Thesis_Status.id.desc()).limit(1).scalar_subquery()
    )


def admin_scope():
    return Thesis.query


def supervised_scope(user_id):
    return Thesis.query.filter(Thesis.id.in_(select(Thesis_Supervisor.thesis_id).where(Thesis_Supervisor.supervisor_id == user_id)))


def _active(q):
    return q.filter(Thesis.frozen.isnot(True))


def _student_match(like):
    return Thesis.author_id.in_(select(User_mgmt.id).where(or_(
        User_mgmt.name.ilike(like, escape="\\"), User_mgmt.surname.ilike(like, escape="\\"), User_mgmt.email.ilike(like, escape="\\"),
    )))


def apply_filters(q, args, show_supervisors=False):
    """Apply the board's search/filter parameters (same semantics the old client-side filters had)."""
    text = (args.get("q") or "").strip().lower()
    for term in text.split()[:8]:
        like = _like(term)
        conds = [
            Thesis.title.ilike(like, escape="\\"),
            Thesis.topic.ilike(like, escape="\\"),
            _student_match(like),
            exists().where(Thesis_Tag.thesis_id == Thesis.id, Thesis_Tag.tag.ilike(like, escape="\\")),
        ]
        if show_supervisors:
            conds.append(Thesis.id.in_(
                select(Thesis_Supervisor.thesis_id).join(User_mgmt, User_mgmt.id == Thesis_Supervisor.supervisor_id)
                .where(User_mgmt.surname.ilike(like, escape="\\"))
            ))
        q = q.filter(or_(*conds))
    state = args.get("state")
    if state == "assigned":
        q = q.filter(Thesis.author_id.isnot(None))
    elif state == "open":
        q = q.filter(Thesis.author_id.is_(None))
    level = (args.get("level") or "").strip().lower()
    if level:
        q = q.filter(func.lower(func.coalesce(Thesis.level, "")) == level)
    status = (args.get("status") or "").strip().lower()
    if status == "__none":
        q = q.filter(_latest_status().is_(None))
    elif status:
        q = q.filter(func.lower(_latest_status()) == status)
    vis = args.get("visibility")
    if vis in ("0", "1"):
        q = q.filter(Thesis.is_public.is_(vis == "1"))
    if args.get("interest") == "pending":
        q = q.filter(Thesis.author_id.is_(None),
                     exists().where(Thesis_Interest.thesis_id == Thesis.id, Thesis_Interest.status == "pending"))
    topic = (args.get("topic") or "").strip().lower()
    if topic:
        like = _like(topic)
        q = q.filter(or_(Thesis.topic.ilike(like, escape="\\"),
                         exists().where(Thesis_Tag.thesis_id == Thesis.id, Thesis_Tag.tag.ilike(like, escape="\\"))))
    student = (args.get("student") or "").strip().lower()
    if student:
        q = q.filter(_student_match(_like(student)))
    return q


def _order(q, sort):
    if sort == "title":
        return q.order_by(func.lower(Thesis.title), Thesis.id)
    if sort == "level":
        return q.order_by(func.lower(func.coalesce(Thesis.level, "")), func.lower(Thesis.title), Thesis.id)
    if sort == "progress":
        total = select(func.count(Todo.id)).where(Todo.thesis_id == Thesis.id).scalar_subquery()
        done = select(func.count(Todo.id)).where(Todo.thesis_id == Thesis.id, Todo.status == "completed").scalar_subquery()
        progress = case((Thesis.author_id.is_(None), -1), (total > 0, done * 100.0 / total), else_=-1)
        return q.order_by(progress.desc(), Thesis.id)
    return q.order_by(Thesis.created_at.desc(), Thesis.id.desc())


def board_stats(scope):
    active = _active(scope)
    ids = active.with_entities(Thesis.id).subquery()
    assigned = active.filter(Thesis.author_id.isnot(None)).count()
    total = active.count()
    pending = (
        db.session.query(func.count(Thesis_Interest.id))
        .join(Thesis, Thesis.id == Thesis_Interest.thesis_id)
        .filter(Thesis_Interest.thesis_id.in_(select(ids.c.id)), Thesis.author_id.is_(None), Thesis_Interest.status == "pending")
        .scalar()
    )
    return {"active": total, "assigned": assigned, "open": total - assigned, "pending_interests": pending or 0}


def board_context(scope):
    """Everything the board page itself needs (stats, filter options, archived list)."""
    ids = scope.with_entities(Thesis.id).subquery()
    status_options = sorted(
        s for (s,) in db.session.query(_latest_status()).select_from(Thesis).filter(Thesis.id.in_(select(ids.c.id))).distinct() if s
    )
    archived_theses = scope.filter(Thesis.frozen.is_(True)).all()
    return {
        "stats": board_stats(scope),
        "status_options": status_options,
        "archived": build_thesis_cards(archived_theses)[1],
    }


def board_page(scope, args, page, per, show_supervisors=False):
    """(total, cards) for one page of active theses matching the filters."""
    q = apply_filters(_active(scope), args, show_supervisors)
    total = q.count()
    pages = max(1, -(-total // per))
    page = max(1, min(page, pages))
    theses = _order(q, args.get("sort")).offset((page - 1) * per).limit(per).all()
    by_id = {c["thesis"].id: c for c in build_thesis_cards(theses)[0]}
    return total, page, pages, [by_id[t.id] for t in theses if t.id in by_id]


def board_response(scope, request, detail_endpoint, show_supervisors=False):
    per = max(1, min(request.args.get("per", 8, type=int), 48))
    total, page, pages, cards = board_page(scope, request.args, request.args.get("page", 1, type=int), per, show_supervisors)
    html = render_template("components/thesis_cards.html", cards=cards, detail_endpoint=detail_endpoint,
                           show_supervisors=show_supervisors, dt=datetime.fromtimestamp)
    return jsonify(total=total, page=page, pages=pages, per=per, html=html)
