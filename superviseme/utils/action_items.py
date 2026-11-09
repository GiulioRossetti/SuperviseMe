"""Turn markdown checklist lines of a meeting note into tasks.

Syntax (one per line):  - [ ] Write related work @due:2026-12-01 @student !high
  @student | @supervisor | @me   who is responsible (default: the other party)
  @due:YYYY-MM-DD                due date
  !low | !medium | !high         priority (default medium)
Checked items ([x]) are ignored.
"""
import re
import time

from superviseme import db
from superviseme.models import MeetingNoteReference, Thesis_Supervisor, Todo
from superviseme.utils.workflow import parse_date

LINE = re.compile(r"^\s*[-*+]\s*\[( |x|X)\]\s+(.+?)\s*$", re.MULTILINE)
DUE = re.compile(r"@due:(\d{4}-\d{2}-\d{2})")
WHO = re.compile(r"@(student|supervisor|me)\b", re.IGNORECASE)
PRIO = re.compile(r"!(low|medium|high)\b", re.IGNORECASE)


def extract_action_items(content):
    items = []
    for done, text in LINE.findall(content or ""):
        due = DUE.search(text)
        who = WHO.search(text)
        prio = PRIO.search(text)
        title = DUE.sub("", WHO.sub("", PRIO.sub("", text))).strip(" -–—")
        if not title:
            continue
        items.append({
            "title": title[:200],
            "done": done.lower() == "x",
            "due": parse_date(due.group(1)) if due else None,
            "who": who.group(1).lower() if who else None,
            "priority": prio.group(1).lower() if prio else "medium",
        })
    return items


def _assignee(item, thesis, actor):
    sup = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).first()
    sup_id = sup.supervisor_id if sup else None
    if item["who"] == "me":
        return actor.id
    if item["who"] == "student":
        return thesis.author_id
    if item["who"] == "supervisor":
        return sup_id
    # default: the other party
    return thesis.author_id if actor.id != thesis.author_id else sup_id


def create_todos_from_note(note, actor):
    """Create tasks for the unchecked items not yet created; returns (created, skipped)."""
    thesis = note.thesis
    existing = {t.title.strip().lower() for t in Todo.query.filter_by(thesis_id=thesis.id).all()}
    now = int(time.time())
    created = skipped = 0
    for item in extract_action_items(note.content):
        if item["done"] or item["title"].lower() in existing:
            skipped += 1
            continue
        todo = Todo(thesis_id=thesis.id, author_id=actor.id, title=item["title"],
                    description=f"From meeting note: {note.title}", priority=item["priority"],
                    status="pending", assigned_to_id=_assignee(item, thesis, actor),
                    due_date=item["due"], created_at=now, updated_at=now)
        db.session.add(todo)
        db.session.flush()
        db.session.add(MeetingNoteReference(meeting_note_id=note.id, todo_id=todo.id, created_at=now))
        existing.add(item["title"].lower())
        created += 1
    db.session.commit()
    return created, skipped
