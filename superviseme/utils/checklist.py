"""End-of-thesis checklist: templates per degree course, instances per thesis."""
import re
import time

from superviseme import db
from superviseme.models import Checklist_Template, Checklist_Template_Item, Thesis_Checklist_Item

DAY = 86400
MAX_ITEMS = 60


def clean_url(raw):
    u = (raw or "").strip()
    return u[:500] if re.match(r"^https?://", u, re.I) else None


def parse_item_lines(text):
    """One step per line: ``Title | 30 | https://...`` -- days before the defense and a link are both optional."""
    out = []
    for line in (text or "").splitlines():
        title, *rest = [p.strip() for p in line.strip().split("|")]
        title = title[:200]
        if not title:
            continue
        days = url = None
        for part in rest:
            if re.fullmatch(r"\d{1,4}", part) and days is None:
                days = int(part)
            elif url is None:
                url = clean_url(part)
        out.append((title, days, url))
    return out[:MAX_ITEMS]


def parse_items(text):
    return [(t, d) for t, d, _u in parse_item_lines(text)]


AUDIENCES = ("student", "supervisor")
MAX_RESOURCES = 30


def parse_resources(text):
    """Lines ``Label | https://... | student|supervisor`` (audience optional = everyone) -> list of dicts."""
    out = []
    for line in (text or "").splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        url = clean_url(parts[1])
        if not parts[0] or not url:
            continue
        audience = parts[2].lower() if len(parts) > 2 and parts[2].lower() in AUDIENCES else None
        out.append({"label": parts[0][:150], "url": url, "audience": audience})
    return out[:MAX_RESOURCES]


def normalize_resources(text):
    return "\n".join(" | ".join(filter(None, (r["label"], r["url"], r["audience"]))) for r in parse_resources(text)) or None


def links_for(thesis, role):
    """Info sites and resources of the templates matching the thesis (its degree course or generic),
    limited to what ``role`` ('student', 'supervisor', 'admin') should see."""
    course = (thesis.degree_course or "").strip().lower()
    seen, info, res = set(), [], []
    for t in templates_for(thesis):
        if (t.degree_course or "").strip() and (t.degree_course or "").strip().lower() != course:
            continue
        if t.info_url and t.info_url not in seen:
            seen.add(t.info_url)
            info.append({"label": t.name, "url": t.info_url})
        for r in parse_resources(t.resources):
            if r["url"] in seen or (r["audience"] and role != "admin" and r["audience"] != ("student" if role == "student" else "supervisor")):
                continue
            seen.add(r["url"])
            res.append(r)
    return info, res


def due_for(defense_date, days_before):
    if defense_date is None or days_before is None:
        return None
    return defense_date - days_before * DAY


def templates_for(thesis):
    """Templates matching the thesis' degree course first, then the generic ones."""
    rows = Checklist_Template.query.order_by(Checklist_Template.name).all()
    course = (thesis.degree_course or "").strip().lower()
    return sorted(rows, key=lambda t: (0 if course and (t.degree_course or "").strip().lower() == course else 1, t.name))


def apply_template(thesis, template):
    """Append the template's steps to the thesis (skipping titles already present). Returns number added."""
    have = {i.title.strip().lower() for i in thesis.checklist}
    pos = max([i.position for i in thesis.checklist] + [-1]) + 1
    added = 0
    for it in template.items:
        if it.title.strip().lower() in have or len(thesis.checklist) + added >= MAX_ITEMS:
            continue
        db.session.add(Thesis_Checklist_Item(thesis_id=thesis.id, title=it.title, position=pos, days_before_defense=it.days_before_defense, url=it.url,
                                             due_date=due_for(thesis.defense_date, it.days_before_defense), created_at=int(time.time())))
        pos += 1
        added += 1
    db.session.commit()
    return added


def recompute_due_dates(thesis):
    for i in thesis.checklist:
        if i.days_before_defense is not None and i.status == "pending":
            i.due_date = due_for(thesis.defense_date, i.days_before_defense)


def progress(thesis):
    items = thesis.checklist
    done = sum(1 for i in items if i.status == "done")
    return {"done": done, "total": len(items)}
