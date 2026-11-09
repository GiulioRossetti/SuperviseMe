"""View-model builders for the student thesis page: status timeline and activity calendar."""
from collections import Counter
from datetime import date, datetime, timedelta

# status key -> (label, icon, colour, rank on the canonical path)
STATUS_META = {
    "thesis accepted": ("Thesis accepted", "fa-handshake", "info", 0),
    "in-progress": ("In progress", "fa-spinner", "primary", 1),
    "needs-revision": ("Needs revision", "fa-pen", "warning", 1),
    "suspended": ("Suspended", "fa-pause-circle", "secondary", 1),
    "approved": ("Approved", "fa-thumbs-up", "success", 2),
    "completed": ("Completed", "fa-flag-checkered", "success", 3),
}
CANONICAL = ["thesis accepted", "in-progress", "approved", "completed"]


def _norm(status):
    return (status or "").strip().lower().replace("_", "-")


def _meta(key):
    return STATUS_META.get(key) or (key.replace("-", " ").title() or "Status", "fa-circle", "secondary", 1)


def build_status_timeline(statuses):
    """statuses: iterable of Thesis_Status. Returns a list of dicts ordered past -> future."""
    history = sorted(statuses or [], key=lambda s: s.updated_at or 0)
    items = []
    seen = set()
    for i, st in enumerate(history):
        key = _norm(st.status)
        label, icon, color, _rank = _meta(key)
        seen.add(key)
        is_last = i == len(history) - 1
        items.append({
            "key": key, "label": label, "icon": icon, "color": color,
            "date": st.updated_at,
            "state": "current" if is_last and key != "completed" else "done",
        })
    if not history:
        return [{"key": k, "label": _meta(k)[0], "icon": _meta(k)[1], "color": _meta(k)[2],
                 "date": None, "state": "upcoming"} for k in CANONICAL]
    current_rank = _meta(items[-1]["key"])[3]
    for key in CANONICAL:
        label, icon, color, rank = _meta(key)
        if rank > current_rank and key not in seen:
            items.append({"key": key, "label": label, "icon": icon, "color": color,
                          "date": None, "state": "upcoming"})
    return items


def build_activity_calendar(events, weeks=53, today=None):
    """events: iterable of unix timestamps. Returns a GitHub-style contribution calendar."""
    today = today or date.today()
    start = today - timedelta(days=today.weekday() + 1 if today.weekday() != 6 else 0)  # Sunday of this week
    start = start - timedelta(weeks=weeks - 1)
    counts = Counter()
    for ts in events:
        if not ts:
            continue
        d = datetime.fromtimestamp(ts).date()
        if start <= d <= today:
            counts[d] += 1
    peak = max(counts.values()) if counts else 0

    def level(n):
        if n == 0:
            return 0
        if peak <= 4:
            return min(n, 4)
        q = n / peak
        return 1 if q <= .25 else 2 if q <= .5 else 3 if q <= .75 else 4

    columns, months = [], []
    cur, last_month = start, None
    for w in range(weeks):
        col = []
        for _d in range(7):
            if cur > today:
                col.append(None)
            else:
                n = counts.get(cur, 0)
                col.append({"date": cur.isoformat(), "count": n, "level": level(n)})
            cur += timedelta(days=1)
        first = next((c for c in col if c), None)
        label = ""
        if first:
            m = date.fromisoformat(first["date"]).month
            if m != last_month and (w > 0 or True):
                label = date.fromisoformat(first["date"]).strftime("%b")
                last_month = m
        months.append(label)
        columns.append(col)

    # streaks
    days_sorted = sorted(d for d, n in counts.items() if n)
    longest = run = 0
    prev = None
    for d in days_sorted:
        run = run + 1 if prev and (d - prev).days == 1 else 1
        longest = max(longest, run)
        prev = d
    current = 0
    d = today if counts.get(today) else today - timedelta(days=1)
    while counts.get(d):
        current += 1
        d -= timedelta(days=1)
    return {
        "columns": columns, "months": months, "total": sum(counts.values()),
        "active_days": len([1 for n in counts.values() if n]),
        "longest_streak": longest, "current_streak": current,
    }
