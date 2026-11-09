"""Role-scoped global search over theses, people, updates, tasks, meeting notes and documents."""
import re

from sqlalchemy import and_, or_

from superviseme.models import (
    MeetingNote,
    Thesis,
    Thesis_Document,
    Thesis_Reviewer,
    Thesis_Supervisor,
    Thesis_Update,
    Todo,
    User_mgmt,
)
from superviseme.utils.profile_access import can_view_profile

LIMIT = 10
MIN_LEN = 2


def _like(term):
    esc = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def accessible_thesis_ids(user):
    """Ids of the theses ``user`` is allowed to read in depth (None = all, for admins)."""
    if user.user_type == "admin":
        return None
    ids = {t.id for t in Thesis.query.filter_by(author_id=user.id)}
    ids |= {r.thesis_id for r in Thesis_Supervisor.query.filter_by(supervisor_id=user.id)}
    ids |= {r.thesis_id for r in Thesis_Reviewer.query.filter_by(reviewer_id=user.id)}
    if user.user_type in ("supervisor", "researcher"):
        ids |= {t.id for t in Thesis.query.filter_by(publisher_id=user.id)}
    return ids


def snippet(text, term, width=70):
    text = re.sub(r"\s+", " ", text or "").strip()
    i = text.lower().find(term.lower())
    if i < 0:
        return text[: width * 2]
    start = max(0, i - width)
    return ("…" if start else "") + text[start : i + len(term) + width] + ("…" if i + len(term) + width < len(text) else "")


def search(user, term):
    term = (term or "").strip()[:100]
    out = {"theses": [], "people": [], "updates": [], "tasks": [], "notes": [], "documents": []}
    if len(term) < MIN_LEN:
        return out
    pat = _like(term)
    ids = accessible_thesis_ids(user)

    # theses: everything the user can access + the public catalog
    q = Thesis.query.filter(or_(Thesis.title.ilike(pat, escape="\\"), Thesis.description.ilike(pat, escape="\\"),
                                Thesis.topic.ilike(pat, escape="\\")))
    if ids is not None:
        public = and_(Thesis.is_public.is_(True), Thesis.author_id.is_(None))
        q = q.filter(or_(Thesis.id.in_(ids), public) if ids else public)
    out["theses"] = q.order_by(Thesis.created_at.desc()).limit(LIMIT).all()

    # people
    cond = [User_mgmt.name.ilike(pat, escape="\\"), User_mgmt.surname.ilike(pat, escape="\\"), User_mgmt.username.ilike(pat, escape="\\")]
    if user.user_type == "admin":
        cond.append(User_mgmt.email.ilike(pat, escape="\\"))
    people = User_mgmt.query.filter(or_(*cond)).order_by(User_mgmt.surname).limit(LIMIT * 3).all()
    out["people"] = [p for p in people if can_view_profile(user, p)][:LIMIT]

    if ids is not None and not ids:
        return out
    f_ids = lambda col: [col.in_(ids)] if ids is not None else []  # noqa: E731
    out["updates"] = Thesis_Update.query.filter(*f_ids(Thesis_Update.thesis_id), Thesis_Update.content.ilike(pat, escape="\\")) \
        .order_by(Thesis_Update.created_at.desc()).limit(LIMIT).all()
    out["tasks"] = Todo.query.filter(*f_ids(Todo.thesis_id), or_(Todo.title.ilike(pat, escape="\\"), Todo.description.ilike(pat, escape="\\"))) \
        .order_by(Todo.created_at.desc()).limit(LIMIT).all()
    out["notes"] = MeetingNote.query.filter(*f_ids(MeetingNote.thesis_id), or_(MeetingNote.title.ilike(pat, escape="\\"), MeetingNote.content.ilike(pat, escape="\\"))) \
        .order_by(MeetingNote.created_at.desc()).limit(LIMIT).all()
    out["documents"] = Thesis_Document.query.filter(*f_ids(Thesis_Document.thesis_id), Thesis_Document.title.ilike(pat, escape="\\")) \
        .order_by(Thesis_Document.created_at.desc()).limit(LIMIT).all()
    return out

