"""Admin: thesis catalog, assignments, tags, statuses.
"""
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from sqlalchemy import select, or_
from sqlalchemy.orm import aliased
from superviseme.models import *
from superviseme.utils.miscellanea import check_privileges
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
from superviseme import db
import datetime
import time

from superviseme.routes.admin import admin, _audit_admin_action


@admin.route("/admin/theses")
@login_required
def theses():
    """
    This route renders the form for creating a new thesis. It checks if the current user has admin privileges.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    from datetime import datetime
    from superviseme.utils.thesis_board import admin_scope, board_context
    students = User_mgmt.query.filter_by(user_type="student").order_by(User_mgmt.surname).all()
    supervisors = User_mgmt.query.filter_by(user_type="supervisor").order_by(User_mgmt.surname).all()
    return render_template("/admin/theses.html", current_user=current_user, **board_context(admin_scope()),
                           students=students, supervisors=supervisors, dt=datetime.fromtimestamp)


@admin.route("/admin/theses/cards")
@login_required
def theses_cards():
    """One page of thesis cards (JSON), filtered and paginated server-side."""
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    from superviseme.utils.thesis_board import admin_scope, board_response
    return board_response(admin_scope(), request, "admin.thesis_detail", show_supervisors=True)


@admin.route("/admin/theses_data", methods=["GET", "POST"])
@login_required
def theses_data():
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    # Handle POST request for inline editing
    if request.method == "POST":
        data = request.get_json()
        thesis_id = data.get("id")
        
        thesis = Thesis.query.get_or_404(thesis_id)
        
        if "title" in data:
            thesis.title = data["title"]
        if "level" in data:
            thesis.level = data["level"]
            
        db.session.commit()
        return {"status": "success"}, 200
    
    # Handle GET request for table data
    Author = aliased(User_mgmt)

    stmt = (
        select(Thesis, Author)
        .outerjoin(Author, Thesis.author_id == Author.id)
    )

    # search filter
    search = request.args.get("search")
    if search:
        stmt = stmt.where(
            or_(
                Author.name.ilike(f"%{search}%"),
                Thesis.level.ilike(f"%{search}%"),
                Thesis.title.ilike(f"%{search}%"),
            )
        )

    # sorting
    sort = request.args.get("sort")
    if sort:
        order = []
        for s in sort.split(","):
            direction = s[0]
            name = s[1:]
            if name not in ["title", "level", "author_cdl"]:
                continue
            
            # Get the correct column from the appropriate model
            if name in ["title", "level"]:
                col = getattr(Thesis, name, None)
            elif name == "author_cdl":
                col = getattr(Author, "cdl", None)
            else:
                col = None
                
            if col is not None:
                col = col.desc() if direction == "-" else col.asc()
                order.append(col)
        if order:
            stmt = stmt.order_by(*order)

    # total count (separate execution if paginated)
    total = db.session.execute(stmt).all()
    total_count = len(total)

    # pagination
    start = request.args.get("start", type=int, default=-1)
    length = request.args.get("length", type=int, default=-1)
    if start != -1 and length != -1:
        stmt = stmt.offset(start).limit(length)

    results = db.session.execute(stmt).all()

    return {
        "total": total_count,
        "data": [
            {
                "thesis_id": thesis.id,
                "title": thesis.title,
                "level": thesis.level,
                "author_cdl": author.cdl if author else None,
                "assigned": "True" if author else "False",
            }
            for thesis, author in results
        ],
    }


@admin.route("/admin/create_thesis", methods=["POST"])
@login_required
def create_thesis():
    """
    This route handles creating a new thesis. It retrieves the necessary data from the form,
    creates a new Thesis object, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
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
    student_id = request.form.get("student_id")
    supervisor_id = request.form.get("supervisor_id")
    level = request.form.get("level")
    status = "thesis accepted"

    if not title or not description:
        flash("All fields are required")
        return redirect(request.referrer)

    normalized_short, normalized_long, normalized_description = normalize_thesis_descriptions(
        short_description=short_description,
        long_description=long_description,
        fallback_description=description,
    )

    try:
        new_thesis = Thesis(
            title=title,
            description=normalized_description,
            short_description=normalized_short,
            long_description=normalized_long,
            topic=(topic or "").strip() or None,
            prerequisites=(prerequisites or "").strip() or None,
            is_public=is_public,
            publisher_id=current_user.id,
            author_id=int(student_id) if student_id != "" else None,
            frozen=False,
            level=level,
            created_at=int(time.time()),
        )
        db.session.add(new_thesis)
        db.session.flush()
        set_thesis_keywords(db, Thesis_Tag, new_thesis.id, keywords)
        db.session.commit()

        # Only create supervisor assignment if supervisor_id is provided
        if supervisor_id and supervisor_id.strip():
            thesis_supervisor = Thesis_Supervisor(
                thesis_id=new_thesis.id,
                supervisor_id=int(supervisor_id),
                assigned_at=int(time.time()),
            )
            db.session.add(thesis_supervisor)
            db.session.commit()

        # Update the thesis status
        new_status = Thesis_Status(
            thesis_id=new_thesis.id,
            status=status,
            updated_at=int(time.time()),
        )
        db.session.add(new_status)
        db.session.commit()

        flash("Thesis created successfully")
        return redirect(url_for("admin.theses"))
    except Exception as e:
        flash(f"Error creating thesis: {e}")
        return redirect(request.referrer)


@admin.route("/admin/update_thesis", methods=["POST"])
@login_required
def update_thesis():
    """
    This route handles updating an existing thesis. It retrieves the necessary data from the form,
    updates the Thesis object, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    payload = request.get_json(silent=True) or {}
    thesis_id = request.form.get("thesis_id") or payload.get("id")
    title = request.form.get("title") or payload.get("title")
    level = request.form.get("level") or payload.get("level")
    description = request.form.get("description") or payload.get("description")
    short_description = request.form.get("short_description") or payload.get("short_description")
    long_description = request.form.get("long_description") or payload.get("long_description")
    topic = request.form.get("topic") or payload.get("topic")
    prerequisites = request.form.get("prerequisites") or payload.get("prerequisites")
    keywords = request.form.get("keywords") or payload.get("keywords")
    is_public_value = request.form.get("is_public")
    if request.is_json and "is_public" in payload:
        is_public_value = payload.get("is_public")

    thesis = Thesis.query.get_or_404(thesis_id)
    
    if title:
        thesis.title = title
    if level:
        thesis.level = level  
    if any(v is not None for v in [description, short_description, long_description]):
        normalized_short, normalized_long, normalized_description = normalize_thesis_descriptions(
            short_description=short_description if short_description is not None else thesis.short_description,
            long_description=long_description if long_description is not None else thesis.long_description,
            fallback_description=description if description is not None else thesis.description,
        )
        thesis.short_description = normalized_short
        thesis.long_description = normalized_long
        thesis.description = normalized_description
    if topic is not None:
        thesis.topic = (topic or "").strip() or None
    if prerequisites is not None:
        thesis.prerequisites = (prerequisites or "").strip() or None
    if request.is_json:
        if "is_public" in payload:
            thesis.is_public = parse_bool(is_public_value)
    else:
        thesis.is_public = parse_bool(is_public_value)
    if thesis.is_public and not thesis.publisher_id:
        thesis.publisher_id = current_user.id
    if keywords is not None:
        set_thesis_keywords(db, Thesis_Tag, thesis.id, keywords)
        
    db.session.commit()
    
    if request.is_json:
        return {"status": "success"}, 200
    
    flash("Thesis updated successfully")
    return redirect(url_for("admin.theses"))


@admin.route("/admin/delete_thesis/<int:thesis_id>", methods=["DELETE"])
@login_required
def delete_thesis(thesis_id):
    """
    This route handles deleting a thesis by its ID. It retrieves the Thesis object,
    deletes it from the database, and redirects to the theses data page.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    success, error = delete_thesis_with_dependencies(thesis_id)
    if not success:
        _audit_admin_action(
            action="delete_thesis",
            target_type="thesis",
            target_id=thesis_id,
            status="failed",
            details={"error": error},
        )
        return {"status": "error", "message": error or "Unable to delete thesis"}, 400

    db.session.commit()
    _audit_admin_action(
        action="delete_thesis",
        target_type="thesis",
        target_id=thesis_id,
        status="success",
    )
    return {"status": "success"}, 200


@admin.route("/admin/thesis/<int:thesis_id>")
@login_required
def thesis_detail(thesis_id):
    """
    This route displays the details of a specific thesis including all related information
    like supervisors, tags, updates, and allows for editing.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    thesis = Thesis.query.get_or_404(thesis_id)
    author = db.session.get(User_mgmt, thesis.author_id) if thesis.author_id else None
    # Fix N+1 query: Fetch supervisors in a single query
    supervisors = User_mgmt.query.join(Thesis_Supervisor, Thesis_Supervisor.supervisor_id == User_mgmt.id)\
        .filter(Thesis_Supervisor.thesis_id == thesis_id).all()
    status_history = Thesis_Status.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Status.updated_at.desc()).all()
    tags = Thesis_Tag.query.filter_by(thesis_id=thesis_id).all()
    updates = Thesis_Update.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Update.created_at.desc()).all()
    interests = Thesis_Interest.query.filter_by(thesis_id=thesis_id, status="pending").order_by(
        Thesis_Interest.created_at.desc()
    ).all()
    
    # Get all students and supervisors for reassignment
    students = User_mgmt.query.filter_by(user_type="student").all()
    all_supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()
    
    objectives = Thesis_Objective.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Objective.created_at.desc()).all()
    hypotheses = Thesis_Hypothesis.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Hypothesis.created_at.desc()).all()
    todos = Todo.query.filter_by(thesis_id=thesis_id).order_by(Todo.created_at.desc()).all()
    meeting_notes = MeetingNote.query.filter_by(thesis_id=thesis_id).order_by(MeetingNote.created_at.desc()).all()
    resources = Resource.query.filter_by(thesis_id=thesis_id).all()
    from superviseme.utils.research_output import linked_outputs
    return render_template("/admin/thesis_detail.html", 
                         current_user=current_user, linked_outputs=linked_outputs(thesis_id=thesis_id),
                         objectives=objectives, hypotheses=hypotheses, todos=todos,
                         meeting_notes=meeting_notes, resources=resources,
                         dt=datetime.datetime.fromtimestamp,
                         thesis=thesis,
                         author=author,
                         supervisors=supervisors,
                         status_history=status_history,
                         tags=tags,
                         updates=updates,
                         interests=interests,
                         students=students,
                         all_supervisors=all_supervisors,
                         datetime=datetime.datetime)


@admin.route("/admin/assign_student", methods=["POST"])
@login_required
def assign_student():
    """
    This route handles assigning or reassigning a student to a thesis.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    student_id = request.form.get("student_id")
    
    thesis = Thesis.query.get_or_404(thesis_id)
    if student_id and not thesis.author_id:
        from superviseme.utils.capacity import active_thesis_message, capacity_message
        over = active_thesis_message(int(student_id), thesis.id) or capacity_message(thesis)
        if over:
            flash(over + " (assigned anyway: administrator override)", "warning")
    thesis.author_id = int(student_id) if student_id else None
    if thesis.author_id:
        close_interests_after_direct_assignment(
            thesis_id=thesis.id,
            assigned_student_id=thesis.author_id,
            handler_id=current_user.id,
        )
    db.session.commit()
    
    flash("Student assignment updated successfully")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/assign_supervisor", methods=["POST"])
@login_required
def assign_supervisor():
    """
    This route handles assigning a supervisor to a thesis.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")
    
    # Check if this supervisor is already assigned
    existing = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id, supervisor_id=supervisor_id).first()
    if not existing:
        new_assignment = Thesis_Supervisor(
            thesis_id=thesis_id,
            supervisor_id=supervisor_id,
            assigned_at=int(time.time())
        )
        db.session.add(new_assignment)
        db.session.commit()
        flash("Supervisor assigned successfully")
    else:
        flash("Supervisor is already assigned to this thesis")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/remove_supervisor", methods=["POST"])
@login_required
def remove_supervisor():
    """
    This route handles removing a supervisor from a thesis.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")
    
    assignment = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id, supervisor_id=supervisor_id).first()
    if assignment:
        db.session.delete(assignment)
        db.session.commit()
        flash("Supervisor removed successfully")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/thesis_interest/assign/<int:interest_id>", methods=["POST"])
@login_required
def assign_thesis_interest(interest_id):
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check

    interest = Thesis_Interest.query.get_or_404(interest_id)
    thesis = Thesis.query.get_or_404(interest.thesis_id)
    if interest.status != "pending":
        flash("This interest request has already been handled.", "info")
        return redirect(url_for("admin.thesis_detail", thesis_id=thesis.id))
    if thesis.author_id:
        flash("Thesis is already assigned.", "warning")
        return redirect(url_for("admin.thesis_detail", thesis_id=thesis.id))

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
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis.id))


@admin.route("/admin/thesis_interest/delete/<int:interest_id>", methods=["POST"])
@login_required
def delete_thesis_interest(interest_id):
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check

    interest = Thesis_Interest.query.get_or_404(interest_id)
    thesis_id = interest.thesis_id
    if interest.status != "pending":
        flash("This interest request has already been handled.", "info")
        return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))
    decline_interest(interest, current_user.id)
    db.session.commit()
    flash("Expression of interest declined.", "info")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/add_thesis_tag", methods=["POST"])
@login_required
def add_thesis_tag():
    """
    This route handles adding tags to a thesis.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    tag = request.form.get("tag")
    
    if tag and thesis_id:
        # Check if tag already exists
        existing_tag = Thesis_Tag.query.filter_by(thesis_id=thesis_id, tag=tag).first()
        if not existing_tag:
            new_tag = Thesis_Tag(
                thesis_id=thesis_id,
                tag=tag
            )
            db.session.add(new_tag)
            db.session.commit()
            flash("Tag added successfully")
        else:
            flash("Tag already exists")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/remove_thesis_tag", methods=["POST"])
@login_required
def remove_thesis_tag():
    """
    This route handles removing tags from a thesis.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    tag_id = request.form.get("tag_id")
    thesis_id = request.form.get("thesis_id")
    
    tag = Thesis_Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    
    flash("Tag removed successfully")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/archive_thesis", methods=["POST"])
@login_required
def archive_thesis():
    """
    This route handles archiving/unarchiving a thesis using the frozen field.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    action = request.form.get("action")  # "archive" or "unarchive"
    
    thesis = Thesis.query.get_or_404(thesis_id)
    thesis.frozen = (action == "archive")
    db.session.commit()
    
    status_text = "archived" if thesis.frozen else "unarchived"
    flash(f"Thesis {status_text} successfully")
    if request.form.get("next") == "list":
        return redirect(url_for("admin.theses"))
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/theses_settings")
@login_required
def theses_settings():
    """
    General Settings page for thesis management configuration.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    # Get statistics for the settings overview
    stats = {
        "total_theses": Thesis.query.count(),
        "assigned_theses": Thesis.query.filter(Thesis.author_id.isnot(None)).count(),
        "available_theses": Thesis.query.filter(Thesis.author_id.is_(None)).count(),
        "frozen_theses": Thesis.query.filter_by(frozen=True).count(),
        "thesis_levels": {
            "bachelor": Thesis.query.filter_by(level="bachelor").count(),
            "master": Thesis.query.filter_by(level="master").count(),
            "other": Thesis.query.filter_by(level="other").count()
        }
    }
    
    return render_template("/admin/theses_settings.html", 
                         current_user=current_user, 
                         stats=stats)


@admin.route("/admin/add_thesis_status", methods=["POST"])
@login_required
def add_thesis_status():
    """
    Add a new status entry to a thesis status history
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    status = request.form.get("status")
    
    if not thesis_id or not status:
        flash("Both thesis ID and status are required")
        return redirect(request.referrer)
    
    try:
        new_status = Thesis_Status(
            thesis_id=int(thesis_id),
            status=status,
            updated_at=int(time.time())
        )
        db.session.add(new_status)
        db.session.commit()
        
        flash(f"Status '{status}' added successfully")
        return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))
    except Exception as e:
        flash(f"Error adding status: {e}")
        return redirect(request.referrer)


@admin.route("/admin/update_thesis_status", methods=["POST"])
@login_required
def update_thesis_status():
    """
    Update an existing thesis status entry
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    status_id = request.form.get("status_id")
    new_status_value = request.form.get("status")
    
    if not status_id or not new_status_value:
        flash("Status ID and new status value are required")
        return redirect(request.referrer)
    
    try:
        status_entry = Thesis_Status.query.get_or_404(status_id)
        status_entry.status = new_status_value
        status_entry.updated_at = int(time.time())
        db.session.commit()
        
        flash(f"Status updated to '{new_status_value}' successfully")
        return redirect(url_for("admin.thesis_detail", thesis_id=status_entry.thesis_id))
    except Exception as e:
        flash(f"Error updating status: {e}")
        return redirect(request.referrer)


@admin.route("/admin/delete_thesis_status", methods=["POST"])
@login_required  
def delete_thesis_status():
    """
    Delete a thesis status entry
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    status_id = request.form.get("status_id")
    
    if not status_id:
        flash("Status ID is required")
        return redirect(request.referrer)
    
    try:
        status_entry = Thesis_Status.query.get_or_404(status_id)
        thesis_id = status_entry.thesis_id
        db.session.delete(status_entry)
        db.session.commit()
        
        flash("Status deleted successfully")
        return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))
    except Exception as e:
        flash(f"Error deleting status: {e}")
        return redirect(request.referrer)
