"""End-of-thesis checklist: templates per degree course, instances per thesis."""
import re
import time

from superviseme import db
from superviseme.models import Checklist_Template, Checklist_Template_Item, Thesis_Checklist_Item

DAY = 86400
MAX_ITEMS = 60


def parse_items(text):
    """One step per line: ``Title | 30`` (optional days before the defense)."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        title, _sep, days = line.partition("|")
        title = title.strip()[:200]
        days = days.strip()
        if not title:
            continue
        out.append((title, int(days) if re.fullmatch(r"\d{1,4}", days) else None))
    return out[:MAX_ITEMS]


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
        db.session.add(Thesis_Checklist_Item(thesis_id=thesis.id, title=it.title, position=pos, days_before_defense=it.days_before_defense,
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
