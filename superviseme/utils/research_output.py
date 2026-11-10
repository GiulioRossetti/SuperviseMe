"""Research output of a project: publications, funding, milestones, datasets, linked theses, public page."""
import re
import time
from datetime import datetime, timezone

from superviseme import db
from superviseme.models import (
    ResearchProject, ResearchProject_Collaborator, ResearchProject_Dataset, ResearchProject_Milestone,
    ResearchProject_Publication, ResearchProject_Review, ResearchProject_Software, ResearchProject_Thesis,
)

PUBLIC_FIELDS = ("description", "funding", "publications", "datasets", "software", "milestones", "collaborators")
DEFAULT_PUBLIC_FIELDS = ("description", "publications", "datasets", "software")
FAIR_FLAGS = ("findable", "accessible", "interoperable", "reusable")
PUB_TYPES = ("article", "conference", "book", "preprint", "report", "thesis", "other")
READ_ONLY_ROLES = ("viewer",)


def role_in(project, user):
    """'owner', a collaborator role, or None (pending invitations give no access)."""
    if project.researcher_id == user.id:
        return "owner"
    c = ResearchProject_Collaborator.query.filter_by(project_id=project.id, collaborator_id=user.id, status="accepted").first()
    return c.role if c else None


def can_read(project, user):
    return role_in(project, user) is not None


def can_write(project, user):
    r = role_in(project, user)
    return r is not None and r not in READ_ONLY_ROLES


def clean_doi(raw):
    d = (raw or "").strip()
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", d, flags=re.I).strip()
    return d if re.match(r"^10\.\d{4,9}/\S+$", d) else None


def safe_url(raw):
    u = (raw or "").strip()
    return u[:500] if re.match(r"^https?://", u, re.I) else None


def parse_date(raw):
    """yyyy-mm-dd -> unix timestamp (UTC noon), or None."""
    try:
        return int(datetime.strptime((raw or "").strip(), "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else ""


def public_fields(project):
    if project.public_fields is None:
        return set(DEFAULT_PUBLIC_FIELDS)
    return {f for f in project.public_fields.split(",") if f in PUBLIC_FIELDS}


# ---- BibTeX ------------------------------------------------------------------------------------------------

def _bib_escape(text):
    return (text or "").replace("{", "\\{").replace("}", "\\}")


def bibtex(publications):
    kinds = {"article": "article", "conference": "inproceedings", "book": "book", "report": "techreport", "thesis": "phdthesis"}
    out, used = [], set()
    for p in publications:
        first = re.sub(r"\W", "", ((p.authors or "").split(",")[0].split(" ")[-1]) or "anon") or "anon"
        base = f"{first}{p.year or 'nd'}"
        key, n = base, 1
        while key in used:
            n += 1
            key = f"{base}{chr(96 + n)}" if n < 27 else f"{base}{n}"
        used.add(key)
        lines = [f"@{kinds.get(p.pub_type, 'misc')}{{{key},", f"  title = {{{_bib_escape(p.title)}}},"]
        if p.authors:
            lines.append("  author = {" + " and ".join(_bib_escape(a.strip()) for a in p.authors.split(",") if a.strip()) + "},")
        if p.year:
            lines.append(f"  year = {{{p.year}}},")
        if p.venue:
            lines.append(f"  journal = {{{_bib_escape(p.venue)}}}," if p.pub_type == "article" else f"  booktitle = {{{_bib_escape(p.venue)}}},")
        if p.doi:
            lines.append(f"  doi = {{{p.doi}}},")
        if p.url:
            lines.append(f"  url = {{{p.url}}},")
        out.append("\n".join(lines).rstrip(",") + "\n}")
    return "\n\n".join(out) + ("\n" if out else "")


def output_bibtex(items, kind):
    """BibTeX for datasets (@misc, type dataset) or software (@software) records."""
    out, used = [], set()
    for it in items:
        base = re.sub(r"\W", "", (it.title or "item").split(" ")[0]) or "item"
        key, n = base, 1
        while key in used:
            n += 1
            key = f"{base}{n}"
        used.add(key)
        lines = [f"@{'software' if kind == 'software' else 'misc'}{{{key},", f"  title = {{{_bib_escape(it.title)}}},"]
        if kind == "software":
            if it.version:
                lines.append(f"  version = {{{_bib_escape(it.version)}}},")
            if it.repo_url:
                lines.append(f"  url = {{{it.repo_url}}},")
            if it.license:
                lines.append(f"  license = {{{_bib_escape(it.license)}}},")
        else:
            lines.append("  howpublished = {Dataset},")
            if it.url:
                lines.append(f"  url = {{{it.url}}},")
            if it.license:
                lines.append(f"  note = {{License: {_bib_escape(it.license)}}},")
        if it.doi:
            lines.append(f"  doi = {{{it.doi}}},")
        out.append("\n".join(lines).rstrip(",") + "\n}")
    return "\n\n".join(out) + ("\n" if out else "")


def crossref_to_fields(meta):
    kind = (meta.get("type") or "").lower()
    pub_type = "conference" if "proceedings" in kind else "book" if "book" in kind else "preprint" if "posted" in kind else \
        "report" if "report" in kind else "article"
    return {
        "title": (meta.get("title") or "")[:300], "authors": ", ".join(meta.get("authors") or [])[:500],
        "year": meta.get("year"), "venue": (meta.get("venue") or "")[:300] or None, "doi": meta.get("doi"),
        "url": meta.get("url"), "pub_type": pub_type,
    }


# ---- cascade ------------------------------------------------------------------------------------------------

def delete_output(project_id):
    """Delete everything that hangs off a project (output tables and the core project workspace rows)."""
    from superviseme.models import (ResearchProject_Hypothesis, ResearchProject_MeetingNote, ResearchProject_MeetingNoteReference,
                                    ResearchProject_Objective, ResearchProject_Resource, ResearchProject_Status,
                                    ResearchProject_Todo, ResearchProject_TodoReference, ResearchProject_Update)
    ids = lambda model: [i for (i,) in db.session.query(model.id).filter_by(project_id=project_id)]  # noqa: E731
    todo_ids, update_ids, note_ids = ids(ResearchProject_Todo), ids(ResearchProject_Update), ids(ResearchProject_MeetingNote)
    if todo_ids or update_ids:
        ResearchProject_TodoReference.query.filter(db.or_(ResearchProject_TodoReference.todo_id.in_(todo_ids),
                                                          ResearchProject_TodoReference.update_id.in_(update_ids))).delete(synchronize_session=False)
    if todo_ids or note_ids:
        ResearchProject_MeetingNoteReference.query.filter(db.or_(ResearchProject_MeetingNoteReference.todo_id.in_(todo_ids),
                                                                 ResearchProject_MeetingNoteReference.meeting_note_id.in_(note_ids))).delete(synchronize_session=False)
    for model in (ResearchProject_Review, ResearchProject_Publication, ResearchProject_Milestone, ResearchProject_Dataset, ResearchProject_Software,
                  ResearchProject_Thesis, ResearchProject_Todo, ResearchProject_Update, ResearchProject_MeetingNote,
                  ResearchProject_Resource, ResearchProject_Objective, ResearchProject_Hypothesis, ResearchProject_Status):
        model.query.filter_by(project_id=project_id).delete(synchronize_session=False)


# ---- portfolio ----------------------------------------------------------------------------------------------

def portfolio(user, projects):
    """Aggregate figures over the projects the researcher owns or collaborates on."""
    from collections import Counter
    from superviseme.models import Thesis_Supervisor, User_mgmt
    ids = [p.id for p in projects]
    by_area = Counter((p.area or "—") for p in projects)
    by_level = Counter((p.level or "—") for p in projects)
    by_state = Counter("frozen" if p.frozen else "active" for p in projects)
    by_year = Counter(datetime.fromtimestamp(p.created_at, timezone.utc).year for p in projects if p.created_at)
    pubs = ResearchProject_Publication.query.filter(ResearchProject_Publication.project_id.in_(ids)).all() if ids else []
    pubs_year = Counter(p.year for p in pubs if p.year)
    freq = Counter()
    if ids:
        for c in ResearchProject_Collaborator.query.filter(ResearchProject_Collaborator.project_id.in_(ids), ResearchProject_Collaborator.status == "accepted"):
            if c.collaborator_id != user.id:
                freq[c.collaborator_id] += 1
        for p in projects:
            if p.researcher_id != user.id:
                freq[p.researcher_id] += 1
    names = {u.id: f"{u.name} {u.surname}" for u in User_mgmt.query.filter(User_mgmt.id.in_(list(freq))).all()} if freq else {}
    now = int(time.time())
    upcoming = (ResearchProject_Milestone.query.filter(ResearchProject_Milestone.project_id.in_(ids), ResearchProject_Milestone.status == "pending")
                .order_by(ResearchProject_Milestone.due_date).limit(8).all()) if ids else []
    funded = [p for p in projects if p.funder or p.grant_id]
    theses = ResearchProject_Thesis.query.filter(ResearchProject_Thesis.project_id.in_(ids)).count() if ids else 0
    return {
        "total": len(projects), "by_area": by_area.most_common(), "by_level": by_level.most_common(),
        "by_state": dict(by_state), "by_year": sorted(by_year.items()),
        "publications": len(pubs), "pubs_year": sorted(pubs_year.items()),
        "datasets": ResearchProject_Dataset.query.filter(ResearchProject_Dataset.project_id.in_(ids)).count() if ids else 0,
        "software": ResearchProject_Software.query.filter(ResearchProject_Software.project_id.in_(ids)).count() if ids else 0,
        "theses": theses, "supervised": Thesis_Supervisor.query.filter_by(supervisor_id=user.id).count(),
        "top_collaborators": [(names.get(uid, "?"), uid, n) for uid, n in freq.most_common(5)],
        "upcoming": upcoming, "overdue": sum(1 for m in upcoming if m.due_date < now), "funded": funded,
        "projects_by_id": {p.id: p for p in projects},
    }


# ---- weekly digest ------------------------------------------------------------------------------------------

def researcher_digest(user, now=None):
    """Plain-text weekly digest: new updates, open todos, milestones due in 14 days, pending invitations."""
    from superviseme.models import ResearchProject_Todo, ResearchProject_Update
    now = now or int(time.time())
    projects = [p for p in ResearchProject.query.all() if can_read(p, user) and not p.frozen]
    ids = [p.id for p in projects]
    pending_inv = ResearchProject_Collaborator.query.filter_by(collaborator_id=user.id, status="pending").count()
    if not ids and not pending_inv:
        return None
    titles = {p.id: p.title for p in projects}
    updates = ResearchProject_Update.query.filter(ResearchProject_Update.project_id.in_(ids), ResearchProject_Update.created_at >= now - 7 * 86400).all() if ids else []
    todos = ResearchProject_Todo.query.filter(ResearchProject_Todo.project_id.in_(ids), ResearchProject_Todo.status == "pending",
                                              ResearchProject_Todo.assigned_to_id == user.id).all() if ids else []
    miles = ResearchProject_Milestone.query.filter(ResearchProject_Milestone.project_id.in_(ids), ResearchProject_Milestone.status == "pending",
                                                   ResearchProject_Milestone.due_date <= now + 14 * 86400).order_by(ResearchProject_Milestone.due_date).all() if ids else []
    lines = [f"Hello {user.name},", "", "Your weekly research summary:", ""]
    lines.append(f"New project updates this week: {len(updates)}")
    for u in updates[:5]:
        lines.append(f"  - {titles.get(u.project_id, '')}")
    lines.append(f"Open to-dos assigned to you: {len(todos)}")
    for t in todos[:5]:
        lines.append(f"  - {t.title} ({titles.get(t.project_id, '')})")
    lines.append(f"Milestones due within 14 days or overdue: {len(miles)}")
    for m in miles[:8]:
        lines.append(f"  - {m.title} ({titles.get(m.project_id, '')}, {iso(m.due_date)}{', OVERDUE' if m.due_date < now else ''})")
    if pending_inv:
        lines.append(f"Project invitations waiting for your answer: {pending_inv}")
    lines += ["", "— SuperviseMe"]
    return {"text": "\n".join(lines), "updates": len(updates), "todos": len(todos), "milestones": len(miles), "invitations": pending_inv}


def agenda_milestones(user, now=None, horizon_days=180):
    """Pending project milestones (overdue or due within the horizon) on projects the user can read."""
    now = now or int(time.time())
    ids = [p.id for p in ResearchProject.query.filter_by(frozen=False).all() if can_read(p, user)]
    if not ids:
        return []
    return (ResearchProject_Milestone.query.filter(
        ResearchProject_Milestone.project_id.in_(ids), ResearchProject_Milestone.status == "pending",
        ResearchProject_Milestone.due_date <= now + horizon_days * 86400)
        .order_by(ResearchProject_Milestone.due_date).all())


# ---- ORCID import ---------------------------------------------------------------------------------------------

AFFILIATION_TYPES = ("employment", "education")
ORCID_TYPE_MAP = {"journal-article": "article", "conference-paper": "conference", "book": "book", "book-chapter": "book",
                  "preprint": "preprint", "report": "report", "dissertation-thesis": "thesis"}


def _ext_ids(activity):
    import json
    try:
        return json.loads(activity.external_ids or "[]") or []
    except ValueError:
        return []


def activity_doi(activity):
    for e in _ext_ids(activity):
        if (e.get("type") or "").lower() == "doi":
            return clean_doi(e.get("value"))
    return None


def orcid_work_candidates(user, project):
    """Imported ORCID works (not funding/affiliations) not yet listed among the project's publications."""
    from superviseme.models import OrcidActivity
    have_doi = {p.doi.lower() for p in project.publications if p.doi}
    have_title = {p.title.strip().lower() for p in project.publications}
    out = []
    for a in OrcidActivity.query.filter(OrcidActivity.user_id == user.id, OrcidActivity.type.notin_(("funding",) + AFFILIATION_TYPES)) \
            .order_by(OrcidActivity.publication_date.desc()):
        doi = activity_doi(a)
        if (doi and doi.lower() in have_doi) or a.title.strip().lower() in have_title:
            continue
        out.append(a)
    return out


def work_fields(activity):
    year = (activity.publication_date or "")[:4]
    return {"title": activity.title[:300], "authors": None, "year": int(year) if year.isdigit() else None, "venue": None,
            "doi": activity_doi(activity), "url": safe_url(activity.url),
            "pub_type": ORCID_TYPE_MAP.get((activity.type or "").lower(), "other")}


def orcid_fundings(user):
    from superviseme.models import OrcidActivity
    return OrcidActivity.query.filter_by(user_id=user.id, type="funding").order_by(OrcidActivity.publication_date.desc()).all()


def funding_fields(activity):
    grant = next((e.get("value") for e in _ext_ids(activity) if (e.get("type") or "").lower() == "grant_number"), None)
    return {"funder": (activity.organization or "")[:200] or None, "grant_id": (grant or "")[:100] or None}


def affiliation_of(user_id):
    """Most recent ORCID-imported employment (organisation name) of a user, or None."""
    from superviseme.models import OrcidActivity
    a = (OrcidActivity.query.filter_by(user_id=user_id, type="employment")
         .order_by(OrcidActivity.publication_date.desc(), OrcidActivity.id.desc()).first())
    return a.organization if a and a.organization else None


# ---- reuse a project as a template ----------------------------------------------------------------------------

def duplicate_project(project, user, title=None, start_date=None):
    """Copy structure (metadata, objectives, hypotheses, open to-dos, milestones) into a new project owned by user."""
    from superviseme.models import ResearchProject_Hypothesis, ResearchProject_Objective, ResearchProject_Todo
    now = int(time.time())
    copy = ResearchProject(title=(title or f"{project.title} (copy)")[:100], description=project.description,
                           researcher_id=user.id, level=project.level, area=project.area, tags=project.tags,
                           created_at=now, funder=None, grant_id=None)
    db.session.add(copy)
    db.session.flush()
    for o in ResearchProject_Objective.query.filter_by(project_id=project.id):
        db.session.add(ResearchProject_Objective(project_id=copy.id, author_id=user.id, title=o.title, description=o.description, created_at=now))
    for h in ResearchProject_Hypothesis.query.filter_by(project_id=project.id):
        db.session.add(ResearchProject_Hypothesis(project_id=copy.id, author_id=user.id, title=h.title, description=h.description, created_at=now))
    for t in ResearchProject_Todo.query.filter_by(project_id=project.id, status="pending"):
        db.session.add(ResearchProject_Todo(project_id=copy.id, author_id=user.id, title=t.title, description=t.description,
                                            priority=t.priority, created_at=now, updated_at=now))
    new_start = parse_date(start_date)
    old_start = parse_date(project.start_date) or (project.milestones[0].due_date if project.milestones else None)
    if new_start and old_start:
        copy.start_date = iso(new_start)
        for m in project.milestones:
            db.session.add(ResearchProject_Milestone(project_id=copy.id, title=m.title, due_date=m.due_date + (new_start - old_start), created_at=now))
    db.session.commit()
    return copy
