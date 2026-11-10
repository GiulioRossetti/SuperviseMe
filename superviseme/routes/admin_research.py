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
                         ResearchProject_Publication.venue.ilike(like), ResearchProject_Publication.doi.ilike(like)))
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
                               filters=filters, total=ResearchProject_Publication.query.count())
    return render_template("admin/research_publications.html", current_user=current_user, pagination=pagination,
                           pubs=pagination.items, years=years, types=ro.PUB_TYPES, filters=filters,
                           total=ResearchProject_Publication.query.count())
