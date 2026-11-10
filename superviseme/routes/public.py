from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from superviseme.models import (
    ResearchProject, Thesis, Thesis_Interest, Thesis_Status, Thesis_Supervisor, Thesis_Tag, User_mgmt,
)
from superviseme.utils.profile_access import can_view_profile

public = Blueprint("public", __name__)


def _normalize_query(value):
    return (value or "").strip()


@public.route("/theses")
def public_thesis_dashboard():
    q = _normalize_query(request.args.get("q"))
    page = max(1, request.args.get("page", 1, type=int))
    per_page = 20
    supervisor = _normalize_query(request.args.get("supervisor"))
    topic = _normalize_query(request.args.get("topic"))
    keywords = _normalize_query(request.args.get("keywords"))

    query = (
        Thesis.query.filter(
            Thesis.is_public.is_(True),
            Thesis.author_id.is_(None),
            or_(Thesis.frozen.is_(False), Thesis.frozen.is_(None)),
        )
        .outerjoin(Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id)
        .outerjoin(User_mgmt, User_mgmt.id == Thesis_Supervisor.supervisor_id)
        .outerjoin(Thesis_Tag, Thesis_Tag.thesis_id == Thesis.id)
    )

    if q:
        like_q = f"%{q}%"
        query = query.filter(
            or_(
                Thesis.title.ilike(like_q),
                Thesis.short_description.ilike(like_q),
                Thesis.long_description.ilike(like_q),
                Thesis.description.ilike(like_q),
                Thesis.topic.ilike(like_q),
                Thesis.prerequisites.ilike(like_q),
                User_mgmt.name.ilike(like_q),
                User_mgmt.surname.ilike(like_q),
                Thesis_Tag.tag.ilike(like_q),
            )
        )

    if supervisor:
        like_supervisor = f"%{supervisor}%"
        query = query.filter(
            or_(
                User_mgmt.name.ilike(like_supervisor),
                User_mgmt.surname.ilike(like_supervisor),
                (User_mgmt.name + " " + User_mgmt.surname).ilike(like_supervisor),
            )
        )

    if topic:
        query = query.filter(Thesis.topic.ilike(f"%{topic}%"))

    if keywords:
        keyword_terms = [k.strip() for k in keywords.split(",") if k.strip()]
        if keyword_terms:
            query = query.filter(
                or_(*[Thesis_Tag.tag.ilike(f"%{term}%") for term in keyword_terms])
            )

    pagination = query.order_by(Thesis.created_at.desc()).distinct().paginate(
        page=page, per_page=per_page, error_out=False
    )
    theses = pagination.items

    # Preload related info for rendering without N+1 in templates.
    thesis_ids = [th.id for th in theses]
    supervisors_by_thesis = {th_id: [] for th_id in thesis_ids}
    tags_by_thesis = {th_id: [] for th_id in thesis_ids}

    if thesis_ids:
        supervisor_rows = (
            Thesis_Supervisor.query.join(User_mgmt, User_mgmt.id == Thesis_Supervisor.supervisor_id)
            .filter(Thesis_Supervisor.thesis_id.in_(thesis_ids))
            .all()
        )
        for row in supervisor_rows:
            supervisors_by_thesis.setdefault(row.thesis_id, []).append(row.supervisor)

        for tag in Thesis_Tag.query.filter(Thesis_Tag.thesis_id.in_(thesis_ids)).all():
            tags_by_thesis.setdefault(tag.thesis_id, []).append(tag.tag)

    # Let staff know when their own theses exist but are not visible to students.
    hidden_own_theses = 0
    if current_user.is_authenticated and current_user.user_type in ("supervisor", "researcher", "admin"):
        hidden_own_theses = Thesis.query.filter(
            Thesis.publisher_id == current_user.id,
            Thesis.author_id.is_(None),
            or_(Thesis.is_public.is_(False), Thesis.frozen.is_(True)),
        ).count()

    return render_template(
        "public/theses_dashboard.html",
        hidden_own_theses=hidden_own_theses,
        theses=theses,
        pagination=pagination,
        supervisors_by_thesis=supervisors_by_thesis,
        tags_by_thesis=tags_by_thesis,
        filters={
            "q": q,
            "supervisor": supervisor,
            "topic": topic,
            "keywords": keywords,
        },
    )


@public.route("/theses/<int:thesis_id>")
def public_thesis_detail(thesis_id):
    thesis = Thesis.query.filter(
        Thesis.id == thesis_id,
        Thesis.is_public.is_(True),
        Thesis.author_id.is_(None),
        or_(Thesis.frozen.is_(False), Thesis.frozen.is_(None)),
    ).first_or_404()

    supervisors = (
        User_mgmt.query.join(Thesis_Supervisor, Thesis_Supervisor.supervisor_id == User_mgmt.id)
        .filter(Thesis_Supervisor.thesis_id == thesis.id)
        .all()
    )
    tags = Thesis_Tag.query.filter_by(thesis_id=thesis.id).all()
    existing_interest = None
    if current_user.is_authenticated and current_user.user_type == "student":
        existing_interest = Thesis_Interest.query.filter_by(
            thesis_id=thesis.id, student_id=current_user.id, status="pending"
        ).first()

    return render_template(
        "public/thesis_detail.html",
        thesis=thesis,
        supervisors=supervisors,
        tags=tags,
        existing_interest=existing_interest,
    )


@public.route("/users/<int:user_id>")
@login_required
def user_profile(user_id):
    """Read-only profile page of a student / supervisor / researcher / admin."""
    target = User_mgmt.query.get_or_404(user_id)
    if not can_view_profile(current_user, target):
        abort(404)
    if target.id == current_user.id:
        return redirect(url_for("profile.profile_page"))
    from superviseme.utils.privacy import log_profile_view
    log_profile_view(current_user, target)
    if target.user_type == "student" and current_user.user_type == "supervisor":
        return redirect(url_for("supervisor.student_profile", student_id=target.id))

    open_theses, assigned_count, archived_count = [], 0, 0
    student_theses = []
    projects_count = 0
    public_projects = []
    if target.user_type == "student":
        for t in Thesis.query.filter_by(author_id=target.id).order_by(Thesis.created_at.desc()).all():
            status = Thesis_Status.query.filter_by(thesis_id=t.id).order_by(Thesis_Status.updated_at.desc()).first()
            sups = [ts.supervisor for ts in Thesis_Supervisor.query.filter_by(thesis_id=t.id).all()]
            student_theses.append({"thesis": t, "status": status.status if status else None, "supervisors": sups})
    else:
        theses = (
            Thesis.query.outerjoin(Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id)
            .filter(or_(Thesis_Supervisor.supervisor_id == target.id, Thesis.publisher_id == target.id))
            .distinct().order_by(Thesis.created_at.desc()).all()
        )
        for t in theses:
            if t.frozen:
                archived_count += 1
            elif t.author_id:
                assigned_count += 1
            elif t.is_public:
                open_theses.append(t)
        if target.user_type == "researcher":
            projects_count = ResearchProject.query.filter_by(researcher_id=target.id).count()
            public_projects = ResearchProject.query.filter_by(researcher_id=target.id, is_public=True).order_by(ResearchProject.title).all()

    return render_template(
        "public/user_profile.html",
        target=target,
        open_theses=open_theses,
        assigned_count=assigned_count,
        archived_count=archived_count,
        student_theses=student_theses,
        projects_count=projects_count,
        public_projects=public_projects,
        link_meta=__import__("superviseme.utils.user_links", fromlist=["x"]).link_meta,
    )


@public.route("/set-lang")
def set_lang():
    """Set the UI language via cookie and redirect back to the referrer."""
    from flask import redirect, make_response
    lang = request.args.get("lang", "en")
    if lang not in ("en", "it"):
        lang = "en"
    next_url = request.referrer or "/"
    resp = make_response(redirect(next_url))
    resp.set_cookie(
        "lang",
        lang,
        max_age=60 * 60 * 24 * 365,  # 1 year
        samesite="Lax",
        httponly=True,
    )
    return resp


@public.route("/projects/<int:project_id>")
def public_project(project_id):
    """Public page of a research project: only the fields its owner chose to show."""
    from superviseme.models import ResearchProject, ResearchProject_Collaborator
    from superviseme.utils import research_output as ro
    project = ResearchProject.query.filter_by(id=project_id, is_public=True).first_or_404()
    fields = ro.public_fields(project)
    collaborators = []
    if "collaborators" in fields:
        collaborators = [(c.collaborator, c.role) for c in
                         ResearchProject_Collaborator.query.filter_by(project_id=project.id, status="accepted") if c.collaborator]
    return render_template("public/project_detail.html", project=project, fields=fields, collaborators=collaborators,
                           milestones=project.milestones if "milestones" in fields else [], iso=ro.iso)


def _public_outputs(project_id):
    from superviseme.models import ResearchProject
    from superviseme.utils import research_output as ro
    project = ResearchProject.query.filter_by(id=project_id, is_public=True).first_or_404()
    return project, ro.public_fields(project), ro


@public.route("/projects/<int:project_id>/outputs.bib")
def public_project_bib(project_id):
    """BibTeX of the publications, datasets and software the owner made public."""
    from flask import Response
    project, fields, ro = _public_outputs(project_id)
    text = ro.all_bibtex(project.publications if "publications" in fields else (), project.datasets if "datasets" in fields else (),
                         project.software if "software" in fields else ())
    if not text:
        abort(404)
    return Response(text, mimetype="application/x-bibtex", headers={"Content-Disposition": f"attachment; filename=project_{project.id}.bib"})


@public.route("/projects/<int:project_id>/software/<int:sid>/codemeta.json")
def public_software_codemeta(project_id, sid):
    import json
    from flask import Response
    from superviseme.models import ResearchProject_Software
    project, fields, ro = _public_outputs(project_id)
    if "software" not in fields:
        abort(404)
    sw = ResearchProject_Software.query.filter_by(id=sid, project_id=project.id).first_or_404()
    return Response(json.dumps(ro.codemeta(sw, project, ro.software_authors(project, fields)), ensure_ascii=False, indent=2),
                    mimetype="application/ld+json")


@public.route("/projects/<int:project_id>/software/<int:sid>/CITATION.cff")
def public_software_cff(project_id, sid):
    from flask import Response
    from superviseme.models import ResearchProject_Software
    project, fields, ro = _public_outputs(project_id)
    if "software" not in fields:
        abort(404)
    sw = ResearchProject_Software.query.filter_by(id=sid, project_id=project.id).first_or_404()
    return Response(ro.citation_cff(sw, project, ro.software_authors(project, fields)), mimetype="text/yaml",
                    headers={"Content-Disposition": "attachment; filename=CITATION.cff"})
