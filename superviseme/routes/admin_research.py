"""Admin: research overview, project catalog/management and publications catalog.
"""
import time

from flask import render_template, redirect, url_for, request, flash, Response, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from superviseme import db
from superviseme.models import *
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils import research_output as ro
from superviseme.routes.admin import admin, _audit_admin_action

PER_PAGE = 20
STATES = ("active", "frozen", "public", "funded")


def _admin_gate():
    gate = check_privileges(current_user.username, role="admin")
    return None if gate is True else gate


def _page():
    return max(request.args.get("page", 1, type=int) or 1, 1)


def _project_query(args):
    """Apply the catalog filters (q, area, level, state, owner) to ResearchProject."""
    q = ResearchProject.query
    term = (args.get("q") or "").strip()
    if term:
        like = f"%{term}%"
        owner_ids = db.session.query(User_mgmt.id).filter(or_(User_mgmt.name.ilike(like), User_mgmt.surname.ilike(like)))
        q = q.filter(or_(ResearchProject.title.ilike(like), ResearchProject.tags.ilike(like),
                         ResearchProject.funder.ilike(like), ResearchProject.grant_id.ilike(like),
                         ResearchProject.researcher_id.in_(owner_ids)))
    if args.get("area"):
        q = q.filter(ResearchProject.area == args["area"])
    if args.get("level"):
        q = q.filter(ResearchProject.level == args["level"])
    if args.get("owner", type=int):
        q = q.filter(ResearchProject.researcher_id == args.get("owner", type=int))
    state = args.get("state")
    if state == "active":
        q = q.filter(or_(ResearchProject.frozen.is_(False), ResearchProject.frozen.is_(None)))
    elif state == "frozen":
        q = q.filter(ResearchProject.frozen.is_(True))
    elif state == "public":
        q = q.filter(ResearchProject.is_public.is_(True))
    elif state == "funded":
        q = q.filter(ResearchProject.funder.isnot(None), ResearchProject.funder != "")
    return q


def research_stats(now=None):
    """Platform-wide research numbers used by the overview and the dashboard."""
    now = now or int(time.time())
    total = ResearchProject.query.count()
    frozen = ResearchProject.query.filter(ResearchProject.frozen.is_(True)).count()
    return {
        "projects": total,
        "active": total - frozen,
        "frozen": frozen,
        "public": ResearchProject.query.filter(ResearchProject.is_public.is_(True)).count(),
        "funded": ResearchProject.query.filter(ResearchProject.funder.isnot(None), ResearchProject.funder != "").count(),
        "publications": ResearchProject_Publication.query.count(),
        "datasets": ResearchProject_Dataset.query.count(),
        "software": ResearchProject_Software.query.count(),
        "linked_theses": ResearchProject_Thesis.query.count(),
        "overdue_milestones": ResearchProject_Milestone.query.filter(
            ResearchProject_Milestone.status == "pending", ResearchProject_Milestone.due_date < now).count(),
        "pending_invitations": ResearchProject_Collaborator.query.filter_by(status="pending").count(),
        "pending_reviews": ResearchProject_Review.query.filter_by(status="pending").count(),
    }


def _breakdown(column, limit=8):
    rows = (db.session.query(column, func.count(ResearchProject.id)).filter(column.isnot(None), column != "")
            .group_by(column).order_by(func.count(ResearchProject.id).desc()).limit(limit).all())
    return [(k, n) for k, n in rows]


@admin.route("/admin/research")
@login_required
def research():
    """Research overview: statistics, items needing attention and the project catalog."""
    gate = _admin_gate()
    if gate is not None:
        return gate
    from superviseme.utils.projects import LEVEL_LABELS, level_label
    now = int(time.time())
    pagination = _project_query(request.args).order_by(ResearchProject.created_at.desc()).paginate(
        page=_page(), per_page=PER_PAGE, error_out=False)
    overdue = (ResearchProject_Milestone.query.filter(ResearchProject_Milestone.status == "pending",
                                                      ResearchProject_Milestone.due_date < now)
               .order_by(ResearchProject_Milestone.due_date).limit(6).all())
    invitations = (ResearchProject_Collaborator.query.filter_by(status="pending")
                   .order_by(ResearchProject_Collaborator.added_at).limit(6).all())
    reviews = ResearchProject_Review.query.filter_by(status="pending").order_by(ResearchProject_Review.created_at).limit(6).all()
    owners = (User_mgmt.query.join(ResearchProject, ResearchProject.researcher_id == User_mgmt.id)
              .group_by(User_mgmt.id).order_by(User_mgmt.surname).all())
    areas = [a for (a,) in db.session.query(ResearchProject.area).filter(ResearchProject.area.isnot(None), ResearchProject.area != "")
             .distinct().order_by(ResearchProject.area).all()]
    filters = {k: request.args.get(k) for k in ("q", "area", "level", "state", "owner") if request.args.get(k)}
    return render_template("admin/research.html", current_user=current_user, stats=research_stats(now),
                           by_area=_breakdown(ResearchProject.area), by_level=_breakdown(ResearchProject.level),
                           pagination=pagination, projects=pagination.items, overdue=overdue, invitations=invitations,
                           reviews=reviews, owners=owners, areas=areas, filters=filters, states=STATES,
                           levels=list(LEVEL_LABELS.items()), level_label=level_label, now=now, iso=ro.iso)


@admin.route("/admin/research/projects/<int:project_id>")
@login_required
def research_project(project_id):
    """Read/manage view of one research project (team, funding, output, milestones, reviews)."""
    gate = _admin_gate()
    if gate is not None:
        return gate
    from superviseme.utils.projects import level_label
    project = ResearchProject.query.get_or_404(project_id)
    team = (ResearchProject_Collaborator.query.filter_by(project_id=project.id)
            .order_by(ResearchProject_Collaborator.added_at).all())
    users = {u.id: u for u in User_mgmt.query.filter(User_mgmt.id.in_([c.collaborator_id for c in team] + [project.researcher_id])).all()}
    researchers = User_mgmt.query.filter_by(user_type="researcher").order_by(User_mgmt.surname).all()
    return render_template("admin/research_project.html", current_user=current_user, project=project, team=team, users=users,
                           researchers=researchers, level_label=level_label, iso=ro.iso, now=int(time.time()),
                           fields=ro.public_fields(project), public_field_names=ro.PUBLIC_FIELDS)


@admin.route("/admin/research/projects/<int:project_id>/freeze", methods=["POST"])
@login_required
def research_project_freeze(project_id):
    gate = _admin_gate()
    if gate is not None:
        return gate
    project = ResearchProject.query.get_or_404(project_id)
    project.frozen = not bool(project.frozen)
    db.session.commit()
    _audit_admin_action("research_project_freeze" if project.frozen else "research_project_unfreeze", "research_project", project.id)
    flash("Project frozen" if project.frozen else "Project unfrozen")
    return redirect(url_for("admin.research_project", project_id=project.id))


@admin.route("/admin/research/projects/<int:project_id>/visibility", methods=["POST"])
@login_required
def research_project_visibility(project_id):
    gate = _admin_gate()
    if gate is not None:
        return gate
    project = ResearchProject.query.get_or_404(project_id)
    project.is_public = not bool(project.is_public)
    db.session.commit()
    _audit_admin_action("research_project_visibility", "research_project", project.id, details={"is_public": project.is_public})
    flash("Public page enabled" if project.is_public else "Public page disabled")
    return redirect(url_for("admin.research_project", project_id=project.id))


@admin.route("/admin/research/projects/<int:project_id>/owner", methods=["POST"])
@login_required
def research_project_owner(project_id):
    """Reassign a project to another researcher (the previous owner stays on as co-investigator)."""
    gate = _admin_gate()
    if gate is not None:
        return gate
    project = ResearchProject.query.get_or_404(project_id)
    new_owner = db.session.get(User_mgmt, request.form.get("new_owner_id", type=int) or 0)
    if not new_owner or new_owner.user_type != "researcher":
        flash("Choose a researcher as the new owner")
        return redirect(url_for("admin.research_project", project_id=project.id))
    if new_owner.id != project.researcher_id:
        old_owner = project.researcher_id
        ResearchProject_Collaborator.query.filter_by(project_id=project.id, collaborator_id=new_owner.id).delete(synchronize_session=False)
        project.researcher_id = new_owner.id
        if not ResearchProject_Collaborator.query.filter_by(project_id=project.id, collaborator_id=old_owner).first():
            db.session.add(ResearchProject_Collaborator(project_id=project.id, collaborator_id=old_owner, role="co-investigator",
                                                        status="accepted", added_at=int(time.time())))
        db.session.commit()
        _audit_admin_action("research_project_reassign", "research_project", project.id,
                            details={"from": old_owner, "to": new_owner.id})
        try:
            from superviseme.utils.notifications import create_notification
            create_notification(recipient_id=new_owner.id, actor_id=current_user.id, notification_type="project_transfer",
                                title=f"You now own project: {project.title}",
                                message=f"An administrator assigned the project \"{project.title}\" to you.",
                                action_url=url_for("researcher.project_detail", project_id=project.id))
        except Exception:
            from flask import current_app
            current_app.logger.exception("Could not notify the new project owner")
        flash("Project reassigned")
    return redirect(url_for("admin.research_project", project_id=project.id))


@admin.route("/admin/research/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def research_project_delete(project_id):
    gate = _admin_gate()
    if gate is not None:
        return gate
    project = ResearchProject.query.get_or_404(project_id)
    title = project.title
    from superviseme.utils.projects import delete_project_cascade
    delete_project_cascade(project)
    _audit_admin_action("research_project_delete", "research_project", project_id, details={"title": title})
    flash("Project deleted")
    return redirect(url_for("admin.research"))


@admin.route("/admin/research/publications")
@login_required
def research_publications():
    """Catalog of the publications recorded on research projects (filterable, BibTeX export)."""
    gate = _admin_gate()
    if gate is not None:
        return gate
    q = ResearchProject_Publication.query.join(ResearchProject, ResearchProject.id == ResearchProject_Publication.project_id)
    term = (request.args.get("q") or "").strip()
    if term:
        like = f"%{term}%"
        q = q.filter(or_(ResearchProject_Publication.title.ilike(like), ResearchProject_Publication.authors.ilike(like),
                         ResearchProject_Publication.venue.ilike(like), ResearchProject_Publication.doi.ilike(like),
                         ro.match_associated("publication", ResearchProject_Publication, like)))
    year = request.args.get("year", type=int)
    if year:
        q = q.filter(ResearchProject_Publication.year == year)
    ptype = request.args.get("type")
    if ptype in ro.PUB_TYPES:
        q = q.filter(ResearchProject_Publication.pub_type == ptype)
    q = q.order_by(ResearchProject_Publication.year.desc(), ResearchProject_Publication.id.desc())
    if request.args.get("format") == "bib":
        _audit_admin_action("research_publications_export", "research_publication")
        return Response(ro.bibtex(q.all()), mimetype="text/plain",
                        headers={"Content-Disposition": "attachment; filename=publications.bib"})
    pagination = q.paginate(page=_page(), per_page=PER_PAGE, error_out=False)
    years = [y for (y,) in db.session.query(ResearchProject_Publication.year).filter(ResearchProject_Publication.year.isnot(None))
             .distinct().order_by(ResearchProject_Publication.year.desc()).all()]
    filters = {k: request.args.get(k) for k in ("q", "year", "type") if request.args.get(k)}
    if request.headers.get("X-Requested-With") == "fetch":
        return render_template("admin/components/research_publications_list.html", pagination=pagination, pubs=pagination.items,
                               lmap=ro.links_map("publication", [p.id for p in pagination.items]),
                               filters=filters, total=ResearchProject_Publication.query.count())
    return render_template("admin/research_publications.html", current_user=current_user, pagination=pagination,
                           pubs=pagination.items, lmap=ro.links_map("publication", [p.id for p in pagination.items]),
                           projects=_all_projects(), years=years, types=ro.PUB_TYPES, filters=filters,
                           total=ResearchProject_Publication.query.count())


@admin.route("/admin/research/datasets", defaults={"kind": "datasets"})
@admin.route("/admin/research/software", defaults={"kind": "software"})
@login_required
def research_outputs(kind):
    """Catalog of the datasets or software recorded on research projects (live filters, BibTeX export)."""
    gate = _admin_gate()
    if gate is not None:
        return gate
    is_sw = kind == "software"
    model = ResearchProject_Software if is_sw else ResearchProject_Dataset
    link = model.repo_url if is_sw else model.url
    q = model.query.join(ResearchProject, ResearchProject.id == model.project_id)
    term = (request.args.get("q") or "").strip()
    if term:
        like = f"%{term}%"
        cols = [model.title, model.doi, model.license, link] + ([model.language, model.description] if is_sw else [])
        q = q.filter(or_(*[c.ilike(like) for c in cols], ro.match_associated(kind[:-1] if kind == "datasets" else kind, model, like)))
    lic = request.args.get("license")
    if lic:
        q = q.filter(model.license == lic)
    q = q.order_by(model.title)
    if request.args.get("format") == "bib":
        _audit_admin_action(f"research_{kind}_export", f"research_{kind}")
        return Response(ro.output_bibtex(q.all(), kind), mimetype="text/plain",
                        headers={"Content-Disposition": f"attachment; filename={kind}.bib"})
    pagination = q.paginate(page=_page(), per_page=PER_PAGE, error_out=False)
    licenses = [l for (l,) in db.session.query(model.license).filter(model.license.isnot(None), model.license != "").distinct().order_by(model.license).all()]
    filters = {k: request.args.get(k) for k in ("q", "license") if request.args.get(k)}
    return render_template("admin/research_outputs.html", current_user=current_user, kind=kind, is_sw=is_sw, pagination=pagination,
                           items=pagination.items, licenses=licenses, lmap=ro.links_map(kind[:-1] if kind == "datasets" else kind, [i.id for i in pagination.items]),
                           projects=_all_projects(), filters=filters, total=model.query.count())


@admin.route("/admin/research/activity")
@login_required
def research_activity():
    """Audit trail of who created, edited, moved, associated or deleted publications, datasets and software."""
    gate = _admin_gate()
    if gate is not None:
        return gate
    import csv, io
    from datetime import datetime
    q = ResearchOutput_Audit.query
    term = (request.args.get("q") or "").strip()
    if term:
        like = f"%{term}%"
        actors = db.session.query(User_mgmt.id).filter(or_(User_mgmt.name.ilike(like), User_mgmt.surname.ilike(like), User_mgmt.username.ilike(like)))
        projs = db.session.query(ResearchProject.id).filter(ResearchProject.title.ilike(like))
        q = q.filter(or_(ResearchOutput_Audit.title.ilike(like), ResearchOutput_Audit.details.ilike(like),
                         ResearchOutput_Audit.actor_id.in_(actors), ResearchOutput_Audit.project_id.in_(projs)))
    for arg, col in (("kind", ResearchOutput_Audit.kind), ("action", ResearchOutput_Audit.action)):
        if request.args.get(arg):
            q = q.filter(col == request.args[arg])
    def _ts(raw, end=False):
        try:
            return int(datetime.strptime(raw, "%Y-%m-%d").timestamp()) + (86400 if end else 0)
        except (TypeError, ValueError):
            return None
    if _ts(request.args.get("from")):
        q = q.filter(ResearchOutput_Audit.created_at >= _ts(request.args["from"]))
    if _ts(request.args.get("to")):
        q = q.filter(ResearchOutput_Audit.created_at < _ts(request.args["to"], end=True))
    q = q.order_by(ResearchOutput_Audit.created_at.desc(), ResearchOutput_Audit.id.desc())
    projects = {p.id: p.title for p in ResearchProject.query.with_entities(ResearchProject.id, ResearchProject.title)}
    filters = {k: request.args.get(k) for k in ("q", "kind", "action", "from", "to") if request.args.get(k)}
    if request.args.get("format") == "csv":
        _audit_admin_action("research_activity_export", "research_output_audit")
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["when", "who", "action", "kind", "title", "project", "details"])
        for e in q.limit(20000).all():
            cells = [datetime.utcfromtimestamp(e.created_at).strftime("%Y-%m-%d %H:%M"), f"{e.actor.name} {e.actor.surname}" if e.actor else "",
                     e.action, e.kind, e.title or "", projects.get(e.project_id, ""), e.details or ""]
            w.writerow([("'" + c) if isinstance(c, str) and c[:1] in "=+-@" else c for c in cells])
        return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=research_activity.csv"})
    pagination = q.paginate(page=_page(), per_page=PER_PAGE, error_out=False)
    return render_template("admin/research_activity.html", current_user=current_user, pagination=pagination, entries=pagination.items,
                           projects=projects, filters=filters, total=ResearchOutput_Audit.query.count(),
                           actions=("create", "update", "delete", "move", "link", "unlink", "import"), kinds=tuple(ro.OUTPUT_MODELS),
                           fmt=lambda ts: datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M"))


# ---- associate output with projects, users and theses ----------------------------------------------------------

def _all_projects():
    return ResearchProject.query.order_by(ResearchProject.title).all()


def _model(kind):
    model = ro.OUTPUT_MODELS.get(kind)
    if model is None:
        abort(404)
    return model


def _fields(kind, f):
    """Validated column values of a new/edited output from a form."""
    title = (f.get("title") or "").strip()[:300]
    doi, lic = ro.clean_doi(f.get("doi")), (f.get("license") or "").strip()[:100] or None
    if kind == "publication":
        year = f.get("year", type=int)
        return {"title": title, "authors": (f.get("authors") or "").strip()[:500] or None, "venue": (f.get("venue") or "").strip()[:300] or None,
                "year": year if year and 1900 <= year <= 2100 else None, "doi": doi, "url": ro.safe_url(f.get("url")),
                "pub_type": f.get("pub_type") if f.get("pub_type") in ro.PUB_TYPES else "article"}
    if kind == "dataset":
        return {"title": title, "doi": doi, "url": ro.safe_url(f.get("url")), "license": lic}
    return {"title": title, "doi": doi, "license": lic, "repo_url": ro.safe_url(f.get("url") or f.get("repo_url")),
            "version": (f.get("version") or "").strip()[:50] or None, "language": (f.get("language") or "").strip()[:100] or None,
            "description": (f.get("description") or "").strip()[:500] or None}


@admin.route("/admin/research/output/<kind>/new", methods=["POST"])
@login_required
def research_output_new(kind):
    gate = _admin_gate()
    if gate is not None:
        return gate
    model = _model(kind)
    project = db.session.get(ResearchProject, request.form.get("project_id", type=int) or 0)
    fields = _fields(kind, request.form)
    back = url_for("admin.research_publications" if kind == "publication" else "admin.research_outputs", **({} if kind == "publication" else {"kind": ro.KIND_PLURAL[kind]}))
    if not project or not fields["title"]:
        flash("A title and a project are required")
        return redirect(back)
    obj = model(project_id=project.id, created_at=int(time.time()), **({"added_by": current_user.id} if hasattr(model, "added_by") else {}), **fields)
    db.session.add(obj)
    db.session.commit()
    _audit_admin_action("research_output_create", f"research_{kind}", obj.id, details={"project_id": project.id})
    ro.audit("create", kind, obj)
    flash("Added")
    return redirect(url_for("admin.research_output", kind=kind, oid=obj.id))


@admin.route("/admin/research/output/<kind>/<int:oid>")
@login_required
def research_output(kind, oid):
    gate = _admin_gate()
    if gate is not None:
        return gate
    obj = _model(kind).query.get_or_404(oid)
    taken_users = {l.user_id for l, _u in ro.links_map(kind, [oid])[oid]["users"]}
    taken_theses = {l.thesis_id for l, _t in ro.links_map(kind, [oid])[oid]["theses"]}
    people = User_mgmt.query.filter(User_mgmt.user_type != "admin").order_by(User_mgmt.surname, User_mgmt.name).all()
    theses = Thesis.query.order_by(Thesis.title).all()
    return render_template("admin/research_output.html", current_user=current_user, kind=kind, obj=obj, links=ro.links_map(kind, [oid])[oid],
                           people=[u for u in people if u.id not in taken_users], theses=[t for t in theses if t.id not in taken_theses],
                           projects=_all_projects(), pub_types=ro.PUB_TYPES, plural=ro.KIND_PLURAL[kind])


@admin.route("/admin/research/output/<kind>/<int:oid>/project", methods=["POST"])
@login_required
def research_output_project(kind, oid):
    gate = _admin_gate()
    if gate is not None:
        return gate
    obj = _model(kind).query.get_or_404(oid)
    project = db.session.get(ResearchProject, request.form.get("project_id", type=int) or 0)
    if project:
        obj.project_id = project.id
        db.session.commit()
        _audit_admin_action("research_output_move", f"research_{kind}", oid, details={"project_id": project.id})
        ro.audit("move", kind, obj, details={"project": project.title})
        flash("Project updated")
    return redirect(url_for("admin.research_output", kind=kind, oid=oid))


@admin.route("/admin/research/output/<kind>/<int:oid>/link", methods=["POST"])
@login_required
def research_output_link_add(kind, oid):
    gate = _admin_gate()
    if gate is not None:
        return gate
    obj = _model(kind).query.get_or_404(oid)
    user = db.session.get(User_mgmt, request.form.get("user_id", type=int) or 0)
    thesis = db.session.get(Thesis, request.form.get("thesis_id", type=int) or 0)
    if not user and not thesis:
        flash("Choose a user or a thesis")
        return redirect(url_for("admin.research_output", kind=kind, oid=oid))
    for col, val in (("user_id", user.id if user else None), ("thesis_id", thesis.id if thesis else None)):
        if val and not ResearchOutput_Link.query.filter_by(kind=kind, output_id=oid, **{col: val}).first():
            db.session.add(ResearchOutput_Link(kind=kind, output_id=oid, created_by=current_user.id, created_at=int(time.time()), **{col: val}))
    db.session.commit()
    _audit_admin_action("research_output_link", f"research_{kind}", oid, details={"user_id": getattr(user, "id", None), "thesis_id": getattr(thesis, "id", None)})
    ro.audit("link", kind, obj, details={"user": f"{user.name} {user.surname}" if user else None, "thesis": thesis.title if thesis else None})
    flash("Association added")
    return redirect(url_for("admin.research_output", kind=kind, oid=oid))


@admin.route("/admin/research/output/<kind>/<int:oid>/link/<int:link_id>/remove", methods=["POST"])
@login_required
def research_output_link_remove(kind, oid, link_id):
    gate = _admin_gate()
    if gate is not None:
        return gate
    obj = _model(kind).query.get(oid)
    link = ResearchOutput_Link.query.filter_by(id=link_id, kind=kind, output_id=oid).first_or_404()
    who = {"user": f"{link.user.name} {link.user.surname}" if link.user else None, "thesis": link.thesis.title if link.thesis else None}
    db.session.delete(link)
    db.session.commit()
    _audit_admin_action("research_output_unlink", f"research_{kind}", oid)
    ro.audit("unlink", kind, obj, details=who)
    return redirect(url_for("admin.research_output", kind=kind, oid=oid))


@admin.route("/admin/research/output/<kind>/<int:oid>/delete", methods=["POST"])
@login_required
def research_output_delete(kind, oid):
    gate = _admin_gate()
    if gate is not None:
        return gate
    obj = _model(kind).query.get_or_404(oid)
    title, project_id = obj.title, obj.project_id
    ResearchOutput_Link.query.filter_by(kind=kind, output_id=oid).delete(synchronize_session=False)
    db.session.delete(obj)
    db.session.commit()
    _audit_admin_action("research_output_delete", f"research_{kind}", oid)
    ro.audit("delete", kind, title=title, project_id=project_id, details={"output_id": oid})
    flash("Deleted")
    return redirect(url_for("admin.research_publications" if kind == "publication" else "admin.research_outputs", **({} if kind == "publication" else {"kind": ro.KIND_PLURAL[kind]})))
