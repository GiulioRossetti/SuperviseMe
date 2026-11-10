"""Possible duplicates among publications, datasets and software, and a guided merge."""
import difflib
import re
import unicodedata

from superviseme import db
from superviseme.models import ResearchOutput_Link
from superviseme.utils import research_output as ro

MAX_ITEMS = 3000
FILL_FIELDS = {
    "publication": ("authors", "year", "venue", "doi", "url"),
    "dataset": ("doi", "url", "license"),
    "software": ("version", "repo_url", "doi", "license", "language", "description"),
}


def norm_title(title):
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def _norm_doi(doi):
    return (doi or "").strip().lower() or None


def find_groups(kind, same_project_only=False, threshold=0.93):
    """[{"items": [...], "reasons": {...}, "same_project": bool}] with at least two records each, largest first."""
    items = ro.OUTPUT_MODELS[kind].query.order_by(ro.OUTPUT_MODELS[kind].id).limit(MAX_ITEMS).all()
    parent = {i.id: i.id for i in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    reasons = {}

    def union(a, b, why):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
        reasons.setdefault(find(a), set()).add(why)

    by_doi, by_title = {}, {}
    for it in items:
        if _norm_doi(it.doi):
            if _norm_doi(it.doi) in by_doi:
                union(by_doi[_norm_doi(it.doi)], it.id, "doi")
            by_doi.setdefault(_norm_doi(it.doi), it.id)
        nt = norm_title(it.title)
        if nt:
            if nt in by_title:
                union(by_title[nt], it.id, "title")
            by_title.setdefault(nt, it.id)
    ordered = sorted((i for i in items if len(norm_title(i.title)) >= 12), key=lambda i: norm_title(i.title))
    for idx, a in enumerate(ordered):
        na = norm_title(a.title)
        for b in ordered[idx + 1: idx + 25]:
            nb = norm_title(b.title)
            if find(a.id) == find(b.id) or na[:4] != nb[:4]:
                continue
            m = difflib.SequenceMatcher(None, na, nb)
            if m.real_quick_ratio() >= threshold and m.quick_ratio() >= threshold and m.ratio() >= threshold:
                union(a.id, b.id, "similar")
    groups = {}
    for it in items:
        groups.setdefault(find(it.id), []).append(it)
    out = []
    for root, members in groups.items():
        if len(members) < 2:
            continue
        why = set()
        for k, v in reasons.items():
            if find(k) == root:
                why |= v
        same = len({m.project_id for m in members}) == 1
        if same_project_only and not same:
            continue
        out.append({"items": members, "reasons": sorted(why), "same_project": same})
    out.sort(key=lambda g: (-len(g["items"]), g["items"][0].id))
    return out


def merge(kind, keeper_id, other_ids):
    """Fold ``other_ids`` into ``keeper_id``: empty fields are filled, associations moved, the others deleted.

    Returns the keeper; raises ValueError for invalid input.
    """
    model = ro.OUTPUT_MODELS[kind]
    keeper = db.session.get(model, keeper_id)
    others = [o for o in (db.session.get(model, i) for i in set(other_ids) if i != keeper_id) if o is not None]
    if keeper is None or not others:
        raise ValueError("Choose the record to keep and at least one duplicate")
    for o in others:
        for f in FILL_FIELDS[kind]:
            if getattr(keeper, f, None) in (None, "") and getattr(o, f, None) not in (None, ""):
                setattr(keeper, f, getattr(o, f))
        if kind == "dataset" and (o.fair or ""):
            flags = {x for x in (keeper.fair or "").split(",") if x} | {x for x in o.fair.split(",") if x}
            keeper.fair = ",".join(x for x in ro.FAIR_FLAGS if x in flags) or None
        have = {(l.user_id, l.thesis_id) for l in ResearchOutput_Link.query.filter_by(kind=kind, output_id=keeper.id)}
        for link in ResearchOutput_Link.query.filter_by(kind=kind, output_id=o.id).all():
            if (link.user_id, link.thesis_id) in have:
                db.session.delete(link)
            else:
                link.output_id = keeper.id
                have.add((link.user_id, link.thesis_id))
        db.session.delete(o)
    db.session.commit()
    return keeper, others
