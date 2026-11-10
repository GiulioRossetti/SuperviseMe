"""Research projects: levels, tags, hierarchy (sub-projects), links, images and structured reports."""
import io
import re
import time
from datetime import datetime, timezone

from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l

from superviseme import db
from superviseme.models import (
    ResearchProject,
    ResearchProject_Collaborator,
    ResearchProject_Hypothesis,
    ResearchProject_Image,
    ResearchProject_Link,
    ResearchProject_MeetingNote,
    ResearchProject_Objective,
    ResearchProject_Resource,
    ResearchProject_Status,
    ResearchProject_Todo,
    ResearchProject_Update,
    User_mgmt,
)
from superviseme.utils.uploads import UploadError, delete_file, save_image

# value -> label. "level" is the granularity of the work: from a whole programme down to a single paper.
PROJECT_LEVELS = [
    ("programme", _l("Research programme")),
    ("research", _l("Research project")),
    ("full-scale", _l("Full-scale study")),
    ("longitudinal", _l("Longitudinal study")),
    ("pilot", _l("Pilot study")),
    ("grant-proposal", _l("Grant proposal")),
    ("journal-article", _l("Journal article")),
    ("conference-paper", _l("Conference paper")),
    ("paper", _l("Paper")),
    ("preprint", _l("Preprint")),
    ("dataset", _l("Dataset")),
    ("software", _l("Software / tool")),
    ("workshop", _l("Workshop / event")),
    ("other", _l("Other")),
]
LEVEL_LABELS = dict(PROJECT_LEVELS)
LINK_RELATIONS = [
    ("related", _l("Related to")),
    ("extends", _l("Extends")),
    ("uses", _l("Uses results of")),
    ("derived", _l("Derived from")),
]
RELATION_LABELS = dict(LINK_RELATIONS)
MAX_PROJECT_IMAGES = 5
PROJECT_IMAGE_MAX_BYTES = 5 * 1024 * 1024
MAX_TAGS = 10
MAX_DEPTH = 5


def level_label(value):
    return str(LEVEL_LABELS.get(value) or (value or "").replace("-", " ").title() or "")


def normalize_tags(raw):
    """'Graph ML, nlp,, NLP' -> 'graph ml,nlp' (lowercase, de-duplicated, capped)."""
    seen, out = set(), []
    for part in re.split(r"[,;\n]", raw or ""):
        t = re.sub(r"\s+", " ", part).strip().lower()[:30]
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return ",".join(out[:MAX_TAGS]) or None


def clean_level(value):
    value = (value or "").strip()
    return value if value in LEVEL_LABELS else (None if not value else "other")


def clean_area(value):
    return (value or "").strip()[:120] or None


# ---- access -------------------------------------------------------------------------------------------------

def user_can_access(user, project):
    if not user.is_authenticated:
        return False
    if user.user_type == "admin" or project.researcher_id == user.id:
        return True
    return ResearchProject_Collaborator.query.filter_by(project_id=project.id, collaborator_id=user.id).first() is not None


def accessible_projects(user):
    """Projects the user owns or collaborates on."""
    ids = {c.project_id for c in ResearchProject_Collaborator.query.filter_by(collaborator_id=user.id)}
    q = ResearchProject.query.filter(db.or_(ResearchProject.researcher_id == user.id,
                                           ResearchProject.id.in_(ids) if ids else db.false()))
    return q.order_by(ResearchProject.title).all()


# ---- hierarchy ----------------------------------------------------------------------------------------------

def ancestors(project):
    chain, node, guard = [], project.parent, 0
    while node is not None and guard < 50:
        chain.append(node)
        node, guard = node.parent, guard + 1
    return chain


def descendants_ids(project):
    out, stack = set(), [project]
    while stack:
        for c in stack.pop().subprojects:
            if c.id not in out:
                out.add(c.id)
                stack.append(c)
    return out


def set_parent(project, parent_id, user):
    """Validate and set the parent. Returns an error message or None."""
    if not parent_id:
        project.parent_id = None
        return None
    try:
        parent = ResearchProject.query.get(int(parent_id))
    except (TypeError, ValueError):
        parent = None
    if not parent or not user_can_access(user, parent):
        return _("Parent project not found.")
    if project.id is not None and (parent.id == project.id or parent.id in descendants_ids(project)):
        return _("A project cannot be nested inside itself or its own sub-projects.")
    if len(ancestors(parent)) + 1 >= MAX_DEPTH:
        return _("Sub-projects can be nested at most %(n)d levels deep.", n=MAX_DEPTH)
    project.parent_id = parent.id
    return None


def project_tree(user, projects=None):
    """Roots -> children ordering used for display; projects whose parent is not visible are treated as roots."""
    projects = projects if projects is not None else accessible_projects(user)
    ids = {p.id for p in projects}
    return [p for p in projects if p.parent_id not in ids]


# ---- links ---------------------------------------------------------------------------------------------------

def linked_projects(project):
    """[(other_project, relation_label, direction, link)] for links in both directions."""
    rows = []
    for l in ResearchProject_Link.query.filter_by(project_id=project.id):
        other = ResearchProject.query.get(l.linked_id)
        if other:
            rows.append((other, RELATION_LABELS.get(l.relation, l.relation), "out", l))
    for l in ResearchProject_Link.query.filter_by(linked_id=project.id):
        other = ResearchProject.query.get(l.project_id)
        if other:
            rows.append((other, RELATION_LABELS.get(l.relation, l.relation), "in", l))
    return rows


def add_link(project, other_id, relation, user):
    try:
        other = ResearchProject.query.get(int(other_id))
    except (TypeError, ValueError):
        other = None
    if not other or not user_can_access(user, other):
        return _("Project not found.")
    if other.id == project.id:
        return _("A project cannot be linked to itself.")
    if relation not in RELATION_LABELS:
        relation = "related"
    exists = ResearchProject_Link.query.filter(
        db.or_(db.and_(ResearchProject_Link.project_id == project.id, ResearchProject_Link.linked_id == other.id),
               db.and_(ResearchProject_Link.project_id == other.id, ResearchProject_Link.linked_id == project.id))).first()
    if exists:
        return _("These projects are already linked.")
    db.session.add(ResearchProject_Link(project_id=project.id, linked_id=other.id, relation=relation, created_at=int(time.time())))
    db.session.commit()
    return None


def remove_link(project, link_id):
    l = ResearchProject_Link.query.get(link_id)
    if not l or project.id not in (l.project_id, l.linked_id):
        return False
    db.session.delete(l)
    db.session.commit()
    return True


# ---- images --------------------------------------------------------------------------------------------------

def add_images(project, files):
    """Store uploaded images; returns (added, errors)."""
    errors, added = [], 0
    pos = max([i.position for i in project.images], default=-1) + 1
    count = len(project.images)
    for f in files:
        if not f or not f.filename:
            continue
        if count + added >= MAX_PROJECT_IMAGES:
            errors.append(_("At most %(n)d images per project.", n=MAX_PROJECT_IMAGES))
            break
        try:
            stored = save_image(f, "project", PROJECT_IMAGE_MAX_BYTES)
        except UploadError as exc:
            errors.append("%s: %s" % (f.filename, exc))
            continue
        db.session.add(ResearchProject_Image(project_id=project.id, filename=stored, position=pos, created_at=int(time.time())))
        pos += 1
        added += 1
    db.session.commit()
    return added, errors


def delete_image(project, image_id):
    img = ResearchProject_Image.query.filter_by(id=image_id, project_id=project.id).first()
    if not img:
        return False
    stored = img.filename
    db.session.delete(img)
    db.session.commit()
    delete_file(stored)
    return True


def delete_project_cascade(project):
    """Detach sub-projects, drop links, images and collaborators, then the project itself."""
    for child in list(project.subprojects):
        child.parent_id = project.parent_id
    ResearchProject_Link.query.filter(db.or_(ResearchProject_Link.project_id == project.id,
                                             ResearchProject_Link.linked_id == project.id)).delete(synchronize_session=False)
    files = [i.filename for i in project.images]
    ResearchProject_Image.query.filter_by(project_id=project.id).delete(synchronize_session=False)
    ResearchProject_Collaborator.query.filter_by(project_id=project.id).delete(synchronize_session=False)
    db.session.delete(project)
    db.session.commit()
    for f in files:
        delete_file(f)


# ---- report --------------------------------------------------------------------------------------------------

def _fmt(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else ""


def _name(user_id):
    u = User_mgmt.query.get(user_id) if user_id else None
    return f"{u.name or ''} {u.surname or ''}".strip() if u else ""


def project_report(project):
    """Plain-data structured snapshot of a project (everything strings/numbers, ready for md/pdf)."""
    st = ResearchProject_Status.query.filter_by(project_id=project.id).order_by(ResearchProject_Status.updated_at.desc()).first()
    todos = ResearchProject_Todo.query.filter_by(project_id=project.id).order_by(ResearchProject_Todo.created_at).all()
    done = sum(1 for t in todos if t.status == "completed")
    return {
        "project": project,
        "title": project.title,
        "level": level_label(project.level),
        "area": project.area or "",
        "tags": project.tag_list,
        "status": st.status if st else "",
        "frozen": bool(project.frozen),
        "owner": _name(project.researcher_id),
        "created": _fmt(project.created_at),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "description": project.description or "",
        "parent": project.parent.title if project.parent else "",
        "subprojects": [(c.title, level_label(c.level)) for c in project.subprojects],
        "links": [(o.title, rel, "→" if d == "out" else "←") for o, rel, d, _l_ in linked_projects(project)],
        "collaborators": [(_name(c.collaborator_id), c.role) for c in
                          ResearchProject_Collaborator.query.filter_by(project_id=project.id)],
        "objectives": [(o.title, o.status, o.description) for o in
                       ResearchProject_Objective.query.filter_by(project_id=project.id).order_by(ResearchProject_Objective.created_at)],
        "hypotheses": [(h.title, h.status, h.description) for h in
                       ResearchProject_Hypothesis.query.filter_by(project_id=project.id).order_by(ResearchProject_Hypothesis.created_at)],
        "tasks": [(t.title, t.status, t.priority, _name(t.assigned_to_id), _fmt(t.due_date)) for t in todos],
        "tasks_done": done,
        "updates": [(_fmt(u.created_at), _name(u.author_id), u.update_type, u.content) for u in
                    ResearchProject_Update.query.filter_by(project_id=project.id).order_by(ResearchProject_Update.created_at.desc()).limit(15)],
        "meetings": [(_fmt(m.created_at), m.title) for m in
                     ResearchProject_MeetingNote.query.filter_by(project_id=project.id).order_by(ResearchProject_MeetingNote.created_at.desc())],
        "resources": [(r.resource_type, r.resource_url, r.description or "") for r in
                      ResearchProject_Resource.query.filter_by(project_id=project.id)],
    }


def _cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def report_markdown(d):
    L = [f"# {d['title']}", ""]
    meta = [("Level", d["level"]), ("Area", d["area"]), ("Status", (d["status"] or "n/a") + (" (frozen)" if d["frozen"] else "")),
            ("Principal researcher", d["owner"]), ("Created", d["created"]), ("Tags", ", ".join(d["tags"])),
            ("Parent project", d["parent"]), ("Generated", d["generated"])]
    L += [f"- **{k}:** {v}" for k, v in meta if v]
    L += ["", "## Description", "", d["description"], ""]

    def section(title, rows, header, fmt):
        if rows:
            L.extend([f"## {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)])
            L.extend("| " + " | ".join(_cell(x) for x in fmt(r)) + " |" for r in rows)
            L.append("")

    section("Sub-projects", d["subprojects"], ["Title", "Level"], lambda r: r)
    section("Linked projects", d["links"], ["Title", "Relation", "Dir."], lambda r: r)
    section("Team", d["collaborators"], ["Name", "Role"], lambda r: r)
    section("Objectives", d["objectives"], ["Objective", "Status", "Description"], lambda r: r)
    section("Hypotheses", d["hypotheses"], ["Hypothesis", "Status", "Description"], lambda r: r)
    if d["tasks"]:
        L.append(f"## Tasks ({d['tasks_done']}/{len(d['tasks'])} completed)\n")
    section("Task list", d["tasks"], ["Task", "Status", "Priority", "Assignee", "Due"], lambda r: r)
    section("Recent updates", d["updates"], ["Date", "Author", "Type", "Content"], lambda r: (r[0], r[1], r[2], r[3][:300]))
    section("Meeting notes", d["meetings"], ["Date", "Title"], lambda r: r)
    section("Resources", d["resources"], ["Type", "URL", "Description"], lambda r: r)
    return "\n".join(L).rstrip() + "\n"


def report_pdf(d):
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=8, leading=10)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.6 * cm,
                            bottomMargin=1.6 * cm, title=f"Project report - {d['title']}")
    P = lambda t, st=small: Paragraph(escape(str(t or "")), st)
    story = [Paragraph(escape(d["title"]), styles["Title"])]
    meta = [("Level", d["level"]), ("Area", d["area"]), ("Status", (d["status"] or "n/a") + (" (frozen)" if d["frozen"] else "")),
            ("Principal researcher", d["owner"]), ("Created", d["created"]), ("Tags", ", ".join(d["tags"])),
            ("Parent project", d["parent"]), ("Generated", d["generated"])]
    story += [Paragraph("<br/>".join(f"<b>{k}:</b> {escape(str(v))}" for k, v in meta if v), styles["BodyText"]), Spacer(1, .3 * cm),
              Paragraph("Description", styles["Heading2"]), Paragraph(escape(d["description"]).replace("\n", "<br/>"), styles["BodyText"])]

    def table(title, header, rows, widths):
        if not rows:
            return
        story.append(Paragraph(escape(title), styles["Heading2"]))
        data = [header] + [[P(c) for c in r] for r in rows]
        tb = Table(data, colWidths=[w * cm for w in widths], repeatRows=1)
        tb.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4e73df")),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey)]))
        story.append(tb)

    table("Sub-projects", ["Title", "Level"], d["subprojects"], [11, 6.8])
    table("Linked projects", ["Title", "Relation", "Dir."], d["links"], [11, 5, 1.8])
    table("Team", ["Name", "Role"], d["collaborators"], [9, 8.8])
    table("Objectives", ["Objective", "Status", "Description"], d["objectives"], [5, 2.2, 10.6])
    table("Hypotheses", ["Hypothesis", "Status", "Description"], d["hypotheses"], [5, 2.2, 10.6])
    table(f"Tasks ({d['tasks_done']}/{len(d['tasks'])} completed)", ["Task", "Status", "Priority", "Assignee", "Due"],
          d["tasks"], [6.4, 2.2, 2, 4.4, 2.8])
    table("Recent updates", ["Date", "Author", "Type", "Content"], [(a, b, c, e[:300]) for a, b, c, e in d["updates"]], [2, 3, 2, 10.8])
    table("Meeting notes", ["Date", "Title"], d["meetings"], [2.5, 15.3])
    table("Resources", ["Type", "URL", "Description"], d["resources"], [2.5, 8, 7.3])
    doc.build(story)
    return buf.getvalue()
