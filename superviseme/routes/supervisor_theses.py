"""Supervisor: thesis management (catalog, assignments, status, media, tags).
"""
from flask import request, render_template, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from superviseme.utils.miscellanea import check_privileges
from superviseme.routes._supervision import ep, supervision_gate
from superviseme.utils.thesis_management import delete_thesis_with_dependencies
from superviseme.utils.thesis_interest import (
    accept_interest_and_close_others,
    close_interests_after_direct_assignment,
    decline_interest,
)
from superviseme.utils.thesis_public import (
    normalize_thesis_descriptions,
    parse_bool,
    set_thesis_keywords,
)
from superviseme.models import *
from superviseme import db
from datetime import datetime
import time
from flask_babel import gettext as _

from superviseme.routes.supervisor import supervisor


@supervisor.route("/supervisor/theses")
@login_required
def theses_data():
    """
    This route is for thesis data. It retrieves all theses supervised by the current user
    and renders them in a template.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Get theses through the supervisor relationship
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id)\
        .options(joinedload(Thesis_Supervisor.thesis).joinedload(Thesis.author))\
        .all()
    from superviseme.utils.thesis_board import build_thesis_cards
    cards, archived = build_thesis_cards([ts.thesis for ts in thesis_supervisors])
    return render_template("supervisor/theses.html", cards=cards, archived=archived, dt=datetime.fromtimestamp)


@supervisor.route("/supervisor/thesis/<thesis_id>")
@login_required
def thesis_detail(thesis_id):
    """
    This route retrieves details of a specific thesis by its ID and renders them in a template.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Check if the thesis is supervised by the current user
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, 
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        abort(404)

    thesis = thesis_supervisor.thesis
    if not thesis:
        abort(404)

    updates = Thesis_Update.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Update.created_at.desc()).all()
    supervisors = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).all()
    author = thesis.author
    thesis_tags = Thesis_Tag.query.filter_by(thesis_id=thesis_id).all()
    interests = Thesis_Interest.query.filter_by(thesis_id=thesis_id, status="pending").order_by(
        Thesis_Interest.created_at.desc()
    ).all()
    resources = Resource.query.filter_by(thesis_id=thesis_id).all()
    
    # Get objectives and hypotheses
    objectives = Thesis_Objective.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Objective.created_at.desc()).all()
    hypotheses = Thesis_Hypothesis.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Hypothesis.created_at.desc()).all()

    # Get all students for assignment dropdown (only students without active thesis assignments)
    available_students = User_mgmt.query.filter(
        User_mgmt.user_type == "student",
        ~User_mgmt.id.in_(
            db.session.query(Thesis.author_id).filter(Thesis.author_id.isnot(None))
        )
    ).all()

    # Get todos for this thesis for reference dropdown
    todos = Todo.query.filter_by(thesis_id=thesis_id).order_by(Todo.created_at.desc()).all()
    
    # Get meeting notes for this thesis
    meeting_notes = MeetingNote.query.filter_by(thesis_id=thesis_id).order_by(MeetingNote.created_at.desc()).all()

    return render_template("supervisor/thesis_detail.html", thesis=thesis, updates=updates,
                           supervisors=supervisors, author=author, objectives=objectives, 
                           hypotheses=hypotheses, thesis_tags=thesis_tags, resources=resources,
                           available_students=available_students, todos=todos, meeting_notes=meeting_notes,
                           interests=interests,
                           dt=datetime.fromtimestamp)


@supervisor.route("/supervisor/tag_thesis", methods=["POST"])
@login_required
def tag_thesis():
    """
    This route handles tagging a thesis. It retrieves the necessary data from the form,
    updates the thesis with the new tags, and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    thesis_id = request.form.get("thesis_id")
    tags = request.form.get("tags", "")

    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, supervisor_id=current_user.id
    ).first()
    if not thesis_supervisor:
        return redirect(url_for('supervisor.theses_data'))

    tag_items = [t.strip() for t in tags.split(",") if t and t.strip()]
    for tag in tag_items:
        existing = Thesis_Tag.query.filter_by(thesis_id=thesis_id, tag=tag).first()
        if not existing:
            db.session.add(Thesis_Tag(thesis_id=thesis_id, tag=tag))

    db.session.commit()
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


@supervisor.route("/supervisor/delete_tag", methods=["POST"])
@login_required
def delete_tag():
    """
    This route handles deleting a tag from a thesis. It retrieves the tag ID from the form,
    deletes the tag from the database, and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    tag_id = request.form.get("tag_id")
    tag = Thesis_Tag.query.get_or_404(tag_id)

    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=tag.thesis_id, supervisor_id=current_user.id
    ).first()
    if thesis_supervisor:
        db.session.delete(tag)
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=tag.thesis_id))

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/create_thesis", methods=["POST"])
@login_required
def create_thesis():
    """
    This route handles creating a new thesis. It retrieves the necessary data from the form,
    creates a new Thesis object, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    title = request.form.get("title")
    description = request.form.get("description")
    short_description = request.form.get("short_description")
    long_description = request.form.get("long_description")
    topic = request.form.get("topic")
    prerequisites = request.form.get("prerequisites")
    is_public = parse_bool(request.form.get("is_public"))
    keywords = request.form.get("keywords")
    level = request.form.get("level")

    normalized_short, normalized_long, normalized_description = normalize_thesis_descriptions(
        short_description=short_description,
        long_description=long_description,
        fallback_description=description,
    )

    new_thesis = Thesis(
        title=title,
        description=normalized_description,
        short_description=normalized_short,
        long_description=normalized_long,
        topic=(topic or "").strip() or None,
        prerequisites=(prerequisites or "").strip() or None,
        is_public=is_public,
        publisher_id=current_user.id,
        level=level,
        created_at=int(time.time())
    )

    db.session.add(new_thesis)
    db.session.flush()  # Get the thesis ID
    
    # Create supervisor relationship
    thesis_supervisor = Thesis_Supervisor(
        thesis_id=new_thesis.id,
        supervisor_id=current_user.id,
        assigned_at=int(time.time())
    )
    
    db.session.add(thesis_supervisor)
    set_thesis_keywords(db, Thesis_Tag, new_thesis.id, keywords)
    db.session.commit()

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/update_thesis", methods=["POST"])
@login_required
def update_thesis():
    """
    This route handles updating an existing thesis. It retrieves the necessary data from the form,
    updates the Thesis object, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    description = request.form.get("description")
    short_description = request.form.get("short_description")
    long_description = request.form.get("long_description")
    topic = request.form.get("topic")
    prerequisites = request.form.get("prerequisites")
    keywords = request.form.get("keywords")
    is_public_value = request.form.get("is_public")
    level = request.form.get("level")

    # Verify supervisor has access to this thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        supervisor_id=current_user.id,
        thesis_id=thesis_id
    ).first()
    
    if not thesis_supervisor:
        flash("Thesis not found or not accessible")
        return redirect(url_for('supervisor.theses_data'))

    thesis = thesis_supervisor.thesis
    thesis.title = title
    normalized_short, normalized_long, normalized_description = normalize_thesis_descriptions(
        short_description=short_description if short_description is not None else thesis.short_description,
        long_description=long_description if long_description is not None else thesis.long_description,
        fallback_description=description if description is not None else thesis.description,
    )
    thesis.description = normalized_description
    thesis.short_description = normalized_short
    thesis.long_description = normalized_long
    thesis.topic = (topic or "").strip() or None
    thesis.prerequisites = (prerequisites or "").strip() or None
    thesis.is_public = parse_bool(is_public_value)
    if thesis.is_public and not thesis.publisher_id:
        thesis.publisher_id = current_user.id
    thesis.level = level
    set_thesis_keywords(db, Thesis_Tag, thesis.id, keywords)
    db.session.commit()
    
    flash("Thesis updated successfully")
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


@supervisor.route("/supervisor/delete_thesis/<int:thesis_id>", methods=["POST", "DELETE"])
@login_required
def delete_thesis(thesis_id):
    """
    This route handles deleting a thesis by its ID. It retrieves the Thesis object,
    deletes it from the database, and redirects to the theses data page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify the thesis is supervised by the current user
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        if request.method == "DELETE":
            return {"status": "error", "message": "Thesis not found or not accessible"}, 404
        flash("Thesis not found or not accessible")
        return redirect(url_for('supervisor.theses_data'))

    success, error = delete_thesis_with_dependencies(thesis_id)
    if not success:
        if request.method == "DELETE":
            return {"status": "error", "message": error or "Unable to delete thesis"}, 400
        flash(f"Error deleting thesis: {error}")
        return redirect(url_for('supervisor.theses_data'))

    db.session.commit()
    if request.method == "DELETE":
        return {"status": "success"}, 200

    flash("Thesis deleted successfully")
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/add_thesis_supervisor", methods=["POST"])
@login_required
def add_thesis_supervisor():
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")

    thesis_supervisor = Thesis_Supervisor(
        thesis_id=thesis_id,
        supervisor_id=supervisor_id,
        assigned_at=int(time.time())
    )
    db.session.add(thesis_supervisor)
    db.session.commit()

    return theses_data()


@supervisor.route("/supervisor/remove_thesis_supervisor", methods=["POST"])
@login_required
def remove_thesis_supervisor():
    """
    This route handles removing a supervisor from a thesis. It retrieves the Thesis_Supervisor object,
    deletes it from the database, and redirects to the theses data page.
    """
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")

    thesis_supervisor = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id, supervisor_id=supervisor_id).first()
    if thesis_supervisor:
        db.session.delete(thesis_supervisor)
        db.session.commit()

    return theses_data()


@supervisor.route("/supervisor/freeze_updates", methods=["POST"])
@login_required
def freeze_updates():
    """
    This route handles freezing updates for a thesis. It retrieves the thesis ID from the form,
    sets the frozen status, and saves it to the database.
    """
    update_id = request.form.get("update_id")
    update = Thesis_Update.query.get_or_404(update_id)
    update.status = "frozen"
    db.session.commit()
    return thesis_detail(update.thesis_id)


@supervisor.route("/supervisor/unfreeze_updates", methods=["POST"])
@login_required
def unfreeze_updates():
    """
    This route handles unfreezing updates for a thesis. It retrieves the thesis ID from the form,
    sets the frozen status to False, and saves it to the database.
    """
    update_id = request.form.get("update_id")
    update = Thesis_Update.query.get_or_404(update_id)
    update.status = "active"
    db.session.commit()
    return thesis_detail(update.thesis_id)


@supervisor.route("/supervisor/freeze_thesis", methods=["POST"])
@login_required
def freeze_thesis():
    """
    This route handles freezing a thesis. It retrieves the thesis ID from the form,
    sets the frozen status, and saves it to the database.
    """
    thesis_id = request.form.get("thesis_id")
    thesis = Thesis.query.get_or_404(thesis_id)
    thesis.frozen = True
    db.session.commit()
    return theses_data()


@supervisor.route("/supervisor/unfreeze_thesis", methods=["POST"])
@login_required
def unfreeze_thesis():
    """
    This route handles unfreezing a thesis. It retrieves the thesis ID from the form,
    sets the frozen status to False, and saves it to the database.
    """
    thesis_id = request.form.get("thesis_id")
    thesis = Thesis.query.get_or_404(thesis_id)
    thesis.frozen = False
    db.session.commit()
    return theses_data()


@supervisor.route("/supervisor/set_advancement_status", methods=["POST"])
@login_required
def set_advancement_status():
    """
    This route handles setting the advancement status of a thesis. It retrieves the thesis ID and status from the form,
    updates the Thesis object, and saves it to the database.
    """
    thesis_id = request.form.get("thesis_id")
    status = request.form.get("status")

    status = Thesis_Status(
        thesis_id=thesis_id,
        status=status,
        updated_at=int(time.time())
    )
    db.session.add(status)
    db.session.commit()

    return theses_data()


@supervisor.route("/supervisor/delete_advancement_status", methods=["POST"])
@login_required
def delete_advancement_status():
    """
    This route handles deleting the advancement status of a thesis. It retrieves the status ID from the form,
    deletes the status from the database, and redirects to the theses data page.
    """
    status_id = request.form.get("status_id")
    status = Thesis_Status.query.get_or_404(status_id)
    db.session.delete(status)
    db.session.commit()

    return theses_data()


@supervisor.route("/supervisor/thesis_unfolding", methods=["POST"])
@login_required
def thesis_unfolding():
    """
    This route handles unfolding a thesis. It retrieves the thesis ID from the form,
    sets the unfolding status, and saves it to the database.
    """
    thesis_id = request.form.get("thesis_id")
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


@supervisor.route("/supervisor/set_thesis_status", methods=["POST"])
@login_required
def set_thesis_status():
    """
    This route handles setting the advancement status of a thesis. It creates or updates
    the thesis status and saves it to the database.
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    status = request.form.get("status")
    
    # Verify the thesis is supervised by the current user
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if thesis_supervisor:
        # Create new status entry
        new_status = Thesis_Status(
            thesis_id=thesis_id,
            status=status,
            updated_at=int(time.time())
        )
        db.session.add(new_status)
        db.session.commit()
        
        return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))
    
    return redirect(url_for(ep('theses')))


@supervisor.route("/supervisor/assign_thesis", methods=["POST"])
@login_required
def assign_thesis():
    """
    This route allows supervisors to assign thesis to students.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    student_id = request.form.get("student_id")
    thesis_id = request.form.get("thesis_id")
    
    # Verify supervisor owns the thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("Thesis not found or not supervised by you")
        return redirect(url_for('supervisor.theses_data'))
    
    # Verify student exists
    student = User_mgmt.query.filter_by(id=student_id, user_type="student").first()
    if not student:
        flash("Student not found")
        return redirect(url_for('supervisor.theses_data'))
    
    # Check if thesis already has an author
    thesis = db.session.get(Thesis, thesis_id)
    if thesis.author_id:
        flash("Thesis is already assigned to a student")
        return redirect(url_for('supervisor.theses_data'))
    
    from superviseme.utils.capacity import active_thesis_message, capacity_message
    over = active_thesis_message(student.id, thesis.id) or capacity_message(thesis)
    if over:
        flash(over, "warning")
        return redirect(url_for('supervisor.theses_data'))

    # Assign thesis to student
    thesis.author_id = student_id
    close_interests_after_direct_assignment(
        thesis_id=thesis.id,
        assigned_student_id=int(student_id),
        handler_id=current_user.id,
    )
    db.session.commit()
    flash(f"Thesis '{thesis.title}' assigned to {student.name} {student.surname}")
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/unassign_thesis/<int:thesis_id>", methods=["POST"])
@login_required
def unassign_thesis(thesis_id):
    """
    This route allows supervisors to unassign thesis from students.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor owns the thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("Thesis not found or not supervised by you")
        return redirect(url_for('supervisor.theses_data'))
    
    thesis = db.session.get(Thesis, thesis_id)
    student_name = ""
    if thesis.author_id:
        student = db.session.get(User_mgmt, thesis.author_id)
        student_name = f"{student.name} {student.surname}" if student else ""
    
    # Unassign thesis
    thesis.author_id = None
    db.session.commit()
    flash(f"Thesis '{thesis.title}' unassigned from {student_name}")
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/thesis_interest/assign/<int:interest_id>", methods=["POST"])
@login_required
def assign_thesis_interest(interest_id):
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check

    interest = Thesis_Interest.query.get_or_404(interest_id)
    thesis = Thesis.query.get_or_404(interest.thesis_id)
    if thesis.publisher_id != current_user.id:
        flash("Only the thesis publisher can handle interests for this thesis.", "warning")
        return redirect(url_for(ep('thesis_detail'), thesis_id=thesis.id))
    if interest.status != "pending":
        flash("This interest request has already been handled.", "info")
        return redirect(url_for(ep('thesis_detail'), thesis_id=thesis.id))
    if thesis.author_id:
        flash("Thesis is already assigned.", "warning")
        return redirect(url_for(ep('thesis_detail'), thesis_id=thesis.id))

    from superviseme.utils.capacity import active_thesis_message, capacity_message
    over = active_thesis_message(interest.student_id, thesis.id) or capacity_message(thesis)
    if over:
        flash(over, "warning")
        return redirect(url_for(ep('thesis_detail'), thesis_id=thesis.id))

    thesis.author_id = interest.student_id
    db.session.add(
        Thesis_Status(
            thesis_id=thesis.id,
            status="thesis accepted",
            updated_at=int(time.time()),
        )
    )
    accept_interest_and_close_others(
        thesis_id=thesis.id,
        accepted_interest_id=interest.id,
        handler_id=current_user.id,
    )
    db.session.commit()

    from superviseme.utils.notifications import create_notification

    create_notification(
        recipient_id=interest.student_id,
        actor_id=current_user.id,
        notification_type="thesis_status_change",
        title=f"Thesis assigned: {thesis.title}",
        message="Your interest was accepted and the thesis has been assigned to you.",
        thesis_id=thesis.id,
        action_url="/student/thesis",
    )
    flash("Interest accepted and thesis assigned.", "success")
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis.id))


@supervisor.route("/supervisor/thesis_interest/delete/<int:interest_id>", methods=["POST"])
@login_required
def delete_thesis_interest(interest_id):
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check

    interest = Thesis_Interest.query.get_or_404(interest_id)
    thesis = Thesis.query.get_or_404(interest.thesis_id)
    if thesis.publisher_id != current_user.id:
        flash("Only the thesis publisher can handle interests for this thesis.", "warning")
        return redirect(url_for(ep('thesis_detail'), thesis_id=thesis.id))
    if interest.status != "pending":
        flash("This interest request has already been handled.", "info")
        return redirect(url_for(ep('thesis_detail'), thesis_id=thesis.id))

    decline_interest(interest, current_user.id)
    db.session.commit()
    flash("Expression of interest declined.", "info")
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis.id))


# --- Thesis presentation: images and external reference links -----------------

def _managed_thesis_or_redirect(thesis_id):
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return None, privilege_check
    thesis = db.session.get(Thesis, thesis_id)
    from superviseme.utils.thesis_media import user_manages_thesis
    if not thesis or not user_manages_thesis(current_user, thesis):
        flash(_("Thesis not found or not managed by you"))
        return None, redirect(url_for(ep('theses')))
    return thesis, None


@supervisor.route("/supervisor/thesis/<int:thesis_id>/images", methods=["POST"])
@login_required
def add_thesis_images(thesis_id):
    thesis, bad = _managed_thesis_or_redirect(thesis_id)
    if bad:
        return bad
    from superviseme.utils.thesis_media import handle_images_request
    handle_images_request(thesis, request)
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/thesis/<int:thesis_id>/images/<int:image_id>/delete", methods=["POST"])
@login_required
def delete_thesis_image(thesis_id, image_id):
    thesis, bad = _managed_thesis_or_redirect(thesis_id)
    if bad:
        return bad
    from superviseme.utils.thesis_media import delete_image
    flash(_("Image removed.") if delete_image(thesis, image_id) else _("Image not found."))
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/thesis/<int:thesis_id>/links", methods=["POST"])
@login_required
def add_thesis_link(thesis_id):
    thesis, bad = _managed_thesis_or_redirect(thesis_id)
    if bad:
        return bad
    from superviseme.utils.thesis_media import handle_link_request
    handle_link_request(thesis, request)
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/thesis/<int:thesis_id>/links/<int:link_id>/delete", methods=["POST"])
@login_required
def delete_thesis_link(thesis_id, link_id):
    thesis, bad = _managed_thesis_or_redirect(thesis_id)
    if bad:
        return bad
    from superviseme.utils.thesis_media import delete_link
    flash(_("Link removed.") if delete_link(thesis, link_id) else _("Link not found."))
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))
