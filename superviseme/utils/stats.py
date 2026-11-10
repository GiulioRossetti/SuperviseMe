"""Platform statistics for the admin: outputs, projects, theses, supervisors, monthly activity."""
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import func

from superviseme import db
from superviseme.models import (
    ResearchProject, ResearchProject_Dataset, ResearchProject_Publication, ResearchProject_Software, Thesis, Thesis_Status,
    User_mgmt,
)
from superviseme.utils.capacity import capacity_info


def _year(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).year if ts else None


def _month(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m")


def last_months(n=12, now=None):
    d = datetime.fromtimestamp(now or time.time(), tz=timezone.utc)
    y, m, out = d.year, d.month, []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def thesis_states():
    """{"assigned": n, "available": n, "concluded": n, "frozen": n, "by_status": Counter} over all theses."""
    latest = {}
    for ts in Thesis_Status.query.order_by(Thesis_Status.updated_at, Thesis_Status.id).all():
        latest[ts.thesis_id] = ts.status
    out = {"assigned": 0, "available": 0, "concluded": 0, "frozen": 0}
    by_status = Counter()
    for t in Thesis.query.all():
        status = (latest.get(t.id) or "").strip().lower()
        if t.frozen:
            out["frozen"] += 1
        elif status == "completed":
            out["concluded"] += 1
        elif t.author_id:
            out["assigned"] += 1
        else:
            out["available"] += 1
        by_status[status or "n/a"] += 1
    out["total"] = sum(out[k] for k in ("assigned", "available", "concluded", "frozen"))
    out["by_status"] = dict(by_status.most_common())
    return out


def build(since_year=None, now=None):
    now = int(now or time.time())
    pubs = ResearchProject_Publication.query.all()
    datasets = ResearchProject_Dataset.query.all()
    software = ResearchProject_Software.query.all()
    projects = ResearchProject.query.all()
    area_of = {p.id: (p.area or "—") for p in projects}
    title_of = {p.id: p.title for p in projects}

    per_year = defaultdict(lambda: {"publications": 0, "datasets": 0, "software": 0})
    for p in pubs:
        y = p.year or _year(p.created_at)
        if y:
            per_year[y]["publications"] += 1
    for kind, rows in (("datasets", datasets), ("software", software)):
        for r in rows:
            y = _year(r.created_at)
            if y:
                per_year[y][kind] += 1
    years = sorted(y for y in per_year if not since_year or y >= since_year)

    by_area = Counter()
    by_project = Counter()
    for kind_rows in (pubs, datasets, software):
        for r in kind_rows:
            by_area[area_of.get(r.project_id, "—")] += 1
            by_project[r.project_id] += 1
    with_doi = sum(1 for r in (*pubs, *datasets, *software) if r.doi)
    total_out = len(pubs) + len(datasets) + len(software)
    licenses = Counter((r.license or "—") for r in (*datasets, *software))
    fair = Counter(len([f for f in (d.fair or "").split(",") if f]) for d in datasets)

    months = last_months(12, now)
    monthly = {"outputs": Counter(), "theses": Counter(), "projects": Counter()}
    for r in (*pubs, *datasets, *software):
        monthly["outputs"][_month(r.created_at)] += 1
    for t in Thesis.query.with_entities(Thesis.created_at).all():
        monthly["theses"][_month(t[0])] += 1
    for p in projects:
        monthly["projects"][_month(p.created_at)] += 1

    sup = []
    for u in User_mgmt.query.filter(User_mgmt.user_type.in_(("supervisor", "researcher"))).order_by(User_mgmt.surname).all():
        c = capacity_info(u)
        if c["used"] or c["max"] is not None:
            sup.append({"name": f"{u.name or ''} {u.surname or ''}".strip(), "used": c["used"], "max": c["max"], "full": c["full"], "near": c["near"]})
    sup.sort(key=lambda s: (-s["used"], s["name"]))

    people = dict(db.session.query(User_mgmt.user_type, func.count(User_mgmt.id)).group_by(User_mgmt.user_type).all())
    level_counts = Counter((p.level or "—") for p in projects)
    return {
        "people": people,
        "theses": thesis_states(),
        "projects": {"total": len(projects), "frozen": sum(1 for p in projects if p.frozen), "public": sum(1 for p in projects if p.is_public),
                     "by_level": dict(level_counts.most_common())},
        "outputs": {"publications": len(pubs), "datasets": len(datasets), "software": len(software), "total": total_out,
                    "doi_pct": round(100 * with_doi / total_out) if total_out else 0, "licenses": dict(licenses.most_common(8)),
                    "fair": {str(k): fair.get(k, 0) for k in range(5)}},
        "years": years,
        "per_year": {y: per_year[y] for y in years},
        "by_area": dict(by_area.most_common(10)),
        "top_projects": [(title_of.get(pid, "?"), n) for pid, n in by_project.most_common(10)],
        "months": months,
        "monthly": {k: [v.get(m, 0) for m in months] for k, v in monthly.items()},
        "supervisors": sup,
    }


def csv_rows(data):
    """Flat (section, label, series, value) rows of the statistics, for export."""
    rows = []
    for k, v in data["people"].items():
        rows.append(("users", k, "", v))
    for k, v in data["theses"].items():
        if k == "by_status":
            rows += [("thesis_status", s, "", n) for s, n in v.items()]
        else:
            rows.append(("theses", k, "", v))
    for k, v in data["projects"].items():
        if k == "by_level":
            rows += [("project_level", s, "", n) for s, n in v.items()]
        else:
            rows.append(("projects", k, "", v))
    for y, vals in data["per_year"].items():
        rows += [("outputs_per_year", y, kind, n) for kind, n in vals.items()]
    rows += [("outputs_by_area", a, "", n) for a, n in data["by_area"].items()]
    rows += [("top_projects", t, "", n) for t, n in data["top_projects"]]
    rows += [("licenses", l, "", n) for l, n in data["outputs"]["licenses"].items()]
    for kind, series in data["monthly"].items():
        rows += [("monthly_" + kind, m, "", n) for m, n in zip(data["months"], series)]
    rows += [("supervisor_load", s["name"], "limit" if s["max"] is not None else "", s["used"]) for s in data["supervisors"]]
    return rows
