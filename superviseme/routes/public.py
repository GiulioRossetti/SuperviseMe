from flask import Blueprint, render_template, request
from flask_login import current_user
from sqlalchemy import or_

from superviseme.models import Thesis, Thesis_Interest, Thesis_Supervisor, Thesis_Tag, User_mgmt

public = Blueprint("public", __name__)


def _normalize_query(value):
    return (value or "").strip()


@public.route("/theses")
def public_thesis_dashboard():
    q = _normalize_query(request.args.get("q"))
    supervisor = _normalize_query(request.args.get("supervisor"))
    topic = _normalize_query(request.args.get("topic"))
    keywords = _normalize_query(request.args.get("keywords"))

    query = (
        Thesis.query.filter(
            Thesis.is_public.is_(True),
            Thesis.author_id.is_(None),
            Thesis.frozen.is_(False),
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

    theses = query.order_by(Thesis.created_at.desc()).distinct().all()

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

    return render_template(
        "public/theses_dashboard.html",
        theses=theses,
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
    thesis = Thesis.query.filter_by(
        id=thesis_id, is_public=True, author_id=None, frozen=False
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
