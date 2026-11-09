"""View-models for the supervisor/researcher "My theses" board."""
from superviseme.models import Thesis_Interest, Thesis_Status, Todo


def build_thesis_cards(theses):
    """Enrich each thesis with the data shown on its card; returns (active, archived) lists."""
    active, archived = [], []
    seen = set()
    for t in theses:
        if not t or t.id in seen:
            continue
        seen.add(t.id)
        status = Thesis_Status.query.filter_by(thesis_id=t.id).order_by(Thesis_Status.updated_at.desc()).first()
        todos_total = Todo.query.filter_by(thesis_id=t.id).count() if t.author_id else 0
        todos_done = Todo.query.filter_by(thesis_id=t.id, status="completed").count() if todos_total else 0
        pending = Thesis_Interest.query.filter_by(thesis_id=t.id, status="pending").count() if not t.author_id else 0
        card = {
            "thesis": t,
            "student": t.author,
            "state": "frozen" if t.frozen else ("assigned" if t.author_id else "open"),
            "status": status.status if status else None,
            "todos_total": todos_total,
            "todos_done": todos_done,
            "progress": int(round(100 * todos_done / todos_total)) if todos_total else None,
            "pending_interests": pending,
            "keywords": [tag.tag for tag in t.tags],
            "images": len(t.images),
            "links": len(t.links),
        }
        (archived if t.frozen else active).append(card)
    key = lambda c: -(c["thesis"].created_at or 0)
    return sorted(active, key=key), sorted(archived, key=key)
