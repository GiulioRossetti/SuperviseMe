"""Researcher: project research output (publications, funding, milestones, datasets, theses, public page), portfolio."""
import time

from flask import Response, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from superviseme import db
from superviseme.models import (
    ResearchProject, ResearchProject_Collaborator, ResearchProject_Dataset, ResearchProject_Milestone,
    ResearchProject_Publication, ResearchProject_Thesis, Thesis, User_mgmt,
)
from superviseme.routes.researcher import researcher
from superviseme.utils import research_output as ro
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils.projects import accessible_projects
from superviseme.utils.thesis_media import user_manages_thesis


def _load(project_id, write=False, owner=False):
    """(project, gate) — gate is a redirect/403 response when access is denied."""
    gate = check_privileges(current_user.username, role="researcher")
    if gate is not True:
        return None, gate
    project = db.session.get(ResearchProject, project_id)
    if project is None:
        abort(404)
    role = ro.role_in(project, current_user)
    if role is None or (owner and role != "owner") or (write and role in ro.READ_ONLY_ROLES):
        abort(403)
    return project, None


def _back(project):
    return redirect(url_for("researcher.project_output", project_id=project.id))


@researcher.route("/researcher/project/<int:project_id>/output")
@login_required
def project_output(project_id):
    project, gate = _load(project_id)
    if gate is not None:
        return gate
    role = ro.role_in(project, current_user)
    linked = [(l, l.thesis) for l in project.thesis_links if l.thesis]
    linked_ids = {t.id for _l, t in linked}
    candidates = [t for t in Thesis.query.order_by(Thesis.title).all()
                  if t.id not in linked_ids and user_manages_thesis(current_user, t)] if role != "viewer" else []
    collabs = ResearchProject_Collaborator.query.filter_by(project_id=project.id, status="accepted").all()
    return render_template(
        "researcher/project_output.html", project=project, role=role, is_owner=role == "owner",
        can_edit=role not in ro.READ_ONLY_ROLES, linked_theses=linked, thesis_candidates=candidates,
        collab_users=[(db.session.get(User_mgmt, c.collaborator_id), c.role) for c in collabs],
        pub_types=ro.PUB_TYPES, fair_flags=ro.FAIR_FLAGS, public_field_names=ro.PUBLIC_FIELDS,
        public_selected=ro.public_fields(project), iso=ro.iso, now=int(time.time()),
    )


# ---- publications -------------------------------------------------------------------------------------------

@researcher.route("/researcher/project/<int:project_id>/publications/add", methods=["POST"])
@login_required
def add_publication(project_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    f = request.form
    doi_raw = (f.get("doi") or "").strip()
    fields = None
    if doi_raw and not (f.get("title") or "").strip():
        doi = ro.clean_doi(doi_raw)
        if not doi:
            flash("Invalid DOI")
            return _back(project)
        from superviseme.utils.academic_apis import get_crossref_doi
        meta = get_crossref_doi(doi)
        if not meta or not meta.get("title"):
            flash("DOI not found on Crossref: fill in the fields manually")
            return _back(project)
        fields = ro.crossref_to_fields(meta)
    else:
        title = (f.get("title") or "").strip()
        if not title:
            flash("A title or a DOI is required")
            return _back(project)
        year = f.get("year", type=int)
        fields = {
            "title": title[:300], "authors": (f.get("authors") or "").strip()[:500] or None,
            "year": year if year and 1900 <= year <= 2100 else None, "venue": (f.get("venue") or "").strip()[:300] or None,
            "doi": ro.clean_doi(doi_raw), "url": ro.safe_url(f.get("url")),
            "pub_type": f.get("pub_type") if f.get("pub_type") in ro.PUB_TYPES else "article",
        }
    if fields["doi"] and ResearchProject_Publication.query.filter_by(project_id=project.id, doi=fields["doi"]).first():
        flash("This publication is already listed")
        return _back(project)
    db.session.add(ResearchProject_Publication(project_id=project.id, added_by=current_user.id, created_at=int(time.time()), **fields))
    db.session.commit()
    flash("Publication added")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/publications/<int:pub_id>/delete", methods=["POST"])
@login_required
def delete_publication(project_id, pub_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    pub = ResearchProject_Publication.query.filter_by(id=pub_id, project_id=project.id).first_or_404()
    db.session.delete(pub)
    db.session.commit()
    flash("Publication removed")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/publications.bib")
@login_required
def project_publications_bib(project_id):
    project, gate = _load(project_id)
    if gate is not None:
        return gate
    return Response(ro.bibtex(project.publications), mimetype="application/x-bibtex",
                    headers={"Content-Disposition": f"attachment; filename=project-{project.id}.bib"})


@researcher.route("/researcher/publications")
@login_required
def all_publications():
    gate = check_privileges(current_user.username, role="researcher")
    if gate is not True:
        return gate
    projects = accessible_projects(current_user)
    pubs = sorted(((p, pr) for pr in projects for p in pr.publications), key=lambda x: (-(x[0].year or 0), x[0].title))
    if request.args.get("format") == "bib":
        return Response(ro.bibtex([p for p, _pr in pubs]), mimetype="application/x-bibtex",
                        headers={"Content-Disposition": "attachment; filename=publications.bib"})
    return render_template("researcher/publications.html", pubs=pubs)


# ---- funding, milestones ------------------------------------------------------------------------------------

@researcher.route("/researcher/project/<int:project_id>/funding", methods=["POST"])
@login_required
def update_funding(project_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    f = request.form
    project.funder = (f.get("funder") or "").strip()[:200] or None
    project.grant_id = (f.get("grant_id") or "").strip()[:100] or None
    start, end = ro.parse_date(f.get("start_date")), ro.parse_date(f.get("end_date"))
    project.start_date = ro.iso(start) or None
    project.end_date = ro.iso(end) or None
    if start and end and end < start:
        flash("The end date is before the start date")
        db.session.rollback()
        return _back(project)
    db.session.commit()
    flash("Funding details saved")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/milestones/add", methods=["POST"])
@login_required
def add_project_milestone(project_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    title, due = (request.form.get("title") or "").strip(), ro.parse_date(request.form.get("due_date"))
    if not title or due is None:
        flash("A title and a valid due date are required")
        return _back(project)
    db.session.add(ResearchProject_Milestone(project_id=project.id, title=title[:200], due_date=due, created_at=int(time.time())))
    db.session.commit()
    flash("Milestone added")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/milestones/<int:mid>/toggle", methods=["POST"])
@login_required
def toggle_project_milestone(project_id, mid):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    m = ResearchProject_Milestone.query.filter_by(id=mid, project_id=project.id).first_or_404()
    m.status = "pending" if m.status == "done" else "done"
    db.session.commit()
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/milestones/<int:mid>/delete", methods=["POST"])
@login_required
def delete_project_milestone(project_id, mid):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    db.session.delete(ResearchProject_Milestone.query.filter_by(id=mid, project_id=project.id).first_or_404())
    db.session.commit()
    return _back(project)


# ---- datasets -----------------------------------------------------------------------------------------------

@researcher.route("/researcher/project/<int:project_id>/datasets/add", methods=["POST"])
@login_required
def add_dataset(project_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    f = request.form
    title = (f.get("title") or "").strip()
    if not title:
        flash("A title is required")
        return _back(project)
    flags = [x for x in ro.FAIR_FLAGS if f.get(f"fair_{x}")]
    db.session.add(ResearchProject_Dataset(
        project_id=project.id, title=title[:300], doi=ro.clean_doi(f.get("doi")), url=ro.safe_url(f.get("url")),
        license=(f.get("license") or "").strip()[:100] or None, fair=",".join(flags) or None, created_at=int(time.time())))
    db.session.commit()
    flash("Dataset added")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/datasets/<int:did>/delete", methods=["POST"])
@login_required
def delete_dataset(project_id, did):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    db.session.delete(ResearchProject_Dataset.query.filter_by(id=did, project_id=project.id).first_or_404())
    db.session.commit()
    return _back(project)


# ---- linked theses ------------------------------------------------------------------------------------------

@researcher.route("/researcher/project/<int:project_id>/theses/link", methods=["POST"])
@login_required
def link_project_thesis(project_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    thesis = db.session.get(Thesis, request.form.get("thesis_id", type=int) or 0)
    if thesis is None or not user_manages_thesis(current_user, thesis):
        flash("Thesis not found or not managed by you")
        return _back(project)
    if not ResearchProject_Thesis.query.filter_by(project_id=project.id, thesis_id=thesis.id).first():
        db.session.add(ResearchProject_Thesis(project_id=project.id, thesis_id=thesis.id, created_at=int(time.time())))
        db.session.commit()
    flash("Thesis linked")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/theses/<int:link_id>/unlink", methods=["POST"])
@login_required
def unlink_project_thesis(project_id, link_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    db.session.delete(ResearchProject_Thesis.query.filter_by(id=link_id, project_id=project.id).first_or_404())
    db.session.commit()
    return _back(project)


# ---- owner-only: public page, ownership ---------------------------------------------------------------------

@researcher.route("/researcher/project/<int:project_id>/visibility", methods=["POST"])
@login_required
def update_project_visibility(project_id):
    project, gate = _load(project_id, owner=True)
    if gate is not None:
        return gate
    project.is_public = bool(request.form.get("is_public"))
    project.public_fields = ",".join(x for x in ro.PUBLIC_FIELDS if request.form.get(f"show_{x}"))
    db.session.commit()
    flash("Public page settings saved")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/transfer", methods=["POST"])
@login_required
def transfer_project(project_id):
    project, gate = _load(project_id, owner=True)
    if gate is not None:
        return gate
    target_id = request.form.get("new_owner_id", type=int)
    collab = ResearchProject_Collaborator.query.filter_by(project_id=project.id, collaborator_id=target_id or 0, status="accepted").first()
    if not collab:
        flash("The new owner must be an accepted collaborator")
        return _back(project)
    old_owner = project.researcher_id
    project.researcher_id = collab.collaborator_id
    db.session.delete(collab)
    db.session.add(ResearchProject_Collaborator(project_id=project.id, collaborator_id=old_owner, role="co-investigator",
                                                status="accepted", added_at=int(time.time())))
    db.session.commit()
    try:
        from superviseme.utils.notifications import create_notification
        create_notification(recipient_id=collab.collaborator_id, actor_id=current_user.id, notification_type="project_transfer",
                            title=f"You now own project: {project.title}",
                            message=f"{current_user.name} {current_user.surname} transferred the ownership of \"{project.title}\" to you.",
                            action_url=url_for("researcher.project_detail", project_id=project.id))
    except Exception:
        current_app.logger.exception("Could not notify the new project owner")
    flash("Ownership transferred")
    return redirect(url_for("researcher.project_detail", project_id=project.id))


# ---- portfolio ----------------------------------------------------------------------------------------------

@researcher.route("/researcher/portfolio")
@login_required
def portfolio():
    gate = check_privileges(current_user.username, role="researcher")
    if gate is not True:
        return gate
    from superviseme.utils.projects import level_label
    return render_template("researcher/portfolio.html", pf=ro.portfolio(current_user, accessible_projects(current_user)),
                           level_label=level_label, iso=ro.iso, now=int(time.time()))
