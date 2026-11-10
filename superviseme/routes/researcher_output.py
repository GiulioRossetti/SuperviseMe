"""Researcher: project research output (publications, funding, milestones, datasets, theses, public page), portfolio."""
import time

from flask import Response, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from superviseme import db
from superviseme.models import (
    ResearchProject, ResearchProject_Collaborator, ResearchProject_Dataset, ResearchProject_Milestone,
    ResearchProject_Publication, ResearchProject_Resource, ResearchProject_Software, ResearchProject_Review, ResearchProject_Thesis, Thesis, User_mgmt, Notification,
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
    members = [(project.researcher, "owner")] + [(u, r) for u, r in [(db.session.get(User_mgmt, c.collaborator_id), c.role) for c in collabs] if u]
    team = [(u, r, ro.affiliation_of(u.id)) for u, r in members]
    resources = ResearchProject_Resource.query.filter_by(project_id=project.id).order_by(ResearchProject_Resource.created_at.desc()).all()
    return render_template(
        "researcher/project_output.html", project=project, team=team, resources=resources,
        reviewers=[(u, r) for u, r, _a in team if u.id != current_user.id],
        orcid_works=ro.orcid_work_candidates(current_user, project) if role != "viewer" and current_user.orcid_id else [],
        orcid_fundings=ro.orcid_fundings(current_user) if role != "viewer" and current_user.orcid_id else [], role=role, is_owner=role == "owner",
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
    pubs = {p.id: (p, pr) for pr in projects for p in pr.publications}
    for p in ro.linked_for_user(current_user, "publication"):
        pubs.setdefault(p.id, (p, p.project))
    pubs = sorted(pubs.values(), key=lambda x: (-(x[0].year or 0), x[0].title))
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


@researcher.route("/researcher/project/<int:project_id>/datasets/<int:did>/edit", methods=["POST"])
@login_required
def edit_dataset(project_id, did):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    d = ResearchProject_Dataset.query.filter_by(id=did, project_id=project.id).first_or_404()
    f = request.form
    title = (f.get("title") or "").strip()
    if not title:
        flash("A title is required")
        return _back(project)
    d.title = title[:300]
    d.doi = ro.clean_doi(f.get("doi"))
    d.url = ro.safe_url(f.get("url"))
    d.license = (f.get("license") or "").strip()[:100] or None
    d.fair = ",".join(x for x in ro.FAIR_FLAGS if f.get(f"fair_{x}")) or None
    db.session.commit()
    flash("Dataset updated")
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


# ---- software -----------------------------------------------------------------------------------------------

@researcher.route("/researcher/project/<int:project_id>/software/add", methods=["POST"])
@login_required
def add_software(project_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    f = request.form
    title = (f.get("title") or "").strip()
    if not title:
        flash("A title is required")
        return _back(project)
    db.session.add(ResearchProject_Software(
        project_id=project.id, title=title[:300], version=(f.get("version") or "").strip()[:50] or None,
        repo_url=ro.safe_url(f.get("repo_url")), doi=ro.clean_doi(f.get("doi")),
        license=(f.get("license") or "").strip()[:100] or None, language=(f.get("language") or "").strip()[:100] or None,
        description=(f.get("description") or "").strip()[:500] or None, added_by=current_user.id, created_at=int(time.time())))
    db.session.commit()
    flash("Software added")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/software/<int:sid>/edit", methods=["POST"])
@login_required
def edit_software(project_id, sid):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    sw = ResearchProject_Software.query.filter_by(id=sid, project_id=project.id).first_or_404()
    f = request.form
    title = (f.get("title") or "").strip()
    if not title:
        flash("A title is required")
        return _back(project)
    sw.title = title[:300]
    sw.version = (f.get("version") or "").strip()[:50] or None
    sw.repo_url = ro.safe_url(f.get("repo_url"))
    sw.doi = ro.clean_doi(f.get("doi"))
    sw.license = (f.get("license") or "").strip()[:100] or None
    sw.language = (f.get("language") or "").strip()[:100] or None
    sw.description = (f.get("description") or "").strip()[:500] or None
    db.session.commit()
    flash("Software updated")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/software/<int:sid>/delete", methods=["POST"])
@login_required
def delete_software(project_id, sid):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    db.session.delete(ResearchProject_Software.query.filter_by(id=sid, project_id=project.id).first_or_404())
    db.session.commit()
    return _back(project)


def _outputs_page(kind):
    gate = check_privileges(current_user.username, role="researcher")
    if gate is not True:
        return gate
    projects = accessible_projects(current_user)
    attr = "software" if kind == "software" else "datasets"
    found = {o.id: (o, pr) for pr in projects for o in getattr(pr, attr)}
    for o in ro.linked_for_user(current_user, "software" if kind == "software" else "dataset"):
        found.setdefault(o.id, (o, o.project))
    rows = sorted(found.values(), key=lambda x: (x[0].title.lower(), x[0].id))
    if request.args.get("format") == "bib":
        return Response(ro.output_bibtex([o for o, _pr in rows], kind), mimetype="application/x-bibtex",
                        headers={"Content-Disposition": f"attachment; filename={attr}.bib"})
    return render_template("researcher/outputs.html", rows=rows, kind=kind, endpoint=f"researcher.all_{attr}")


@researcher.route("/researcher/datasets")
@login_required
def all_datasets():
    return _outputs_page("datasets")


@researcher.route("/researcher/software")
@login_required
def all_software():
    return _outputs_page("software")


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


# ---- ORCID import (works -> publications, funding -> funding fields) -----------------------------------------

@researcher.route("/researcher/project/<int:project_id>/publications/import_orcid", methods=["POST"])
@login_required
def import_orcid_publications(project_id):
    from superviseme.models import OrcidActivity
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    wanted = {i for i in request.form.getlist("activity_id", type=int)}
    allowed = {a.id: a for a in ro.orcid_work_candidates(current_user, project)}
    added = 0
    for aid in wanted & set(allowed):
        db.session.add(ResearchProject_Publication(project_id=project.id, added_by=current_user.id, created_at=int(time.time()),
                                                   **ro.work_fields(allowed[aid])))
        added += 1
    db.session.commit()
    flash(f"{added} publication(s) imported from ORCID")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/funding/from_orcid", methods=["POST"])
@login_required
def funding_from_orcid(project_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    act = next((a for a in ro.orcid_fundings(current_user) if a.id == request.form.get("activity_id", type=int)), None)
    if act is None:
        flash("Funding entry not found")
        return _back(project)
    fields = ro.funding_fields(act)
    project.funder, project.grant_id = fields["funder"], fields["grant_id"]
    year = (act.publication_date or "")[:4]
    if year.isdigit() and not project.start_date:
        project.start_date = f"{year}-01-01"
    db.session.commit()
    flash("Funding details imported from ORCID")
    return _back(project)


# ---- internal review of resources ---------------------------------------------------------------------------

@researcher.route("/researcher/project/<int:project_id>/reviews/request", methods=["POST"])
@login_required
def request_review(project_id):
    project, gate = _load(project_id, write=True)
    if gate is not None:
        return gate
    resource = ResearchProject_Resource.query.filter_by(id=request.form.get("resource_id", type=int) or 0, project_id=project.id).first()
    reviewer = db.session.get(User_mgmt, request.form.get("reviewer_id", type=int) or 0)
    if resource is None or reviewer is None or reviewer.id == current_user.id or not ro.can_read(project, reviewer):
        flash("Choose a resource and a different member of the team as reviewer")
        return _back(project)
    now = int(time.time())
    if ResearchProject_Review.query.filter_by(resource_id=resource.id, reviewer_id=reviewer.id, status="pending").first():
        flash("This reviewer already has a pending request for this resource")
        return _back(project)
    db.session.add(ResearchProject_Review(project_id=project.id, resource_id=resource.id, requested_by=current_user.id,
                                          reviewer_id=reviewer.id, note=(request.form.get("note") or "").strip()[:2000] or None,
                                          created_at=now, updated_at=now))
    db.session.commit()
    _notify(reviewer.id, "project_review_request", f"Review requested: {project.title}",
            f"{current_user.name} {current_user.surname} asked you to review a resource of \"{project.title}\".",
            url_for("researcher.project_output", project_id=project.id) + "#reviews")
    flash("Review requested")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/reviews/<int:review_id>/decide", methods=["POST"])
@login_required
def decide_review(project_id, review_id):
    project, gate = _load(project_id)
    if gate is not None:
        return gate
    review = ResearchProject_Review.query.filter_by(id=review_id, project_id=project.id).first_or_404()
    if review.reviewer_id != current_user.id:
        abort(403)
    decision = request.form.get("decision")
    if decision not in ("approved", "changes_requested") or review.status != "pending":
        flash("Invalid decision")
        return _back(project)
    review.status, review.updated_at = decision, int(time.time())
    review.comment = (request.form.get("comment") or "").strip()[:4000] or None
    Notification.query.filter_by(recipient_id=current_user.id, notification_type="project_review_request", is_read=False,
                                 action_url=url_for("researcher.project_output", project_id=project.id) + "#reviews"
                                 ).update({"is_read": True}, synchronize_session=False)
    db.session.commit()
    _notify(review.requested_by, "project_review_done", f"Review {decision.replace('_', ' ')}: {project.title}",
            f"{current_user.name} {current_user.surname}: {decision.replace('_', ' ')}.",
            url_for("researcher.project_output", project_id=project.id) + "#reviews")
    flash("Review saved")
    return _back(project)


@researcher.route("/researcher/project/<int:project_id>/reviews/<int:review_id>/delete", methods=["POST"])
@login_required
def delete_review(project_id, review_id):
    project, gate = _load(project_id)
    if gate is not None:
        return gate
    review = ResearchProject_Review.query.filter_by(id=review_id, project_id=project.id).first_or_404()
    if current_user.id not in (review.requested_by, project.researcher_id):
        abort(403)
    db.session.delete(review)
    db.session.commit()
    return _back(project)


def _notify(recipient_id, kind, title, message, url):
    try:
        from superviseme.utils.notifications import create_notification
        create_notification(recipient_id=recipient_id, actor_id=current_user.id, notification_type=kind, title=title,
                            message=message, action_url=url)
    except Exception:
        current_app.logger.exception("Could not send notification")


# ---- reuse a project as a template --------------------------------------------------------------------------

@researcher.route("/researcher/project/<int:project_id>/duplicate", methods=["POST"])
@login_required
def duplicate_project_route(project_id):
    project, gate = _load(project_id)
    if gate is not None:
        return gate
    copy = ro.duplicate_project(project, current_user, (request.form.get("title") or "").strip() or None, request.form.get("start_date"))
    flash("Project created from the template")
    return redirect(url_for("researcher.project_detail", project_id=copy.id))
