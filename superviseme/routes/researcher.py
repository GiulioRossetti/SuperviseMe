from flask import Blueprint, request, render_template, abort, redirect, url_for, jsonify, flash
import logging

logger = logging.getLogger(__name__)
from flask_login import login_required, current_user
from sqlalchemy import select, and_, or_
from superviseme.utils import security
from superviseme.utils.miscellanea import check_privileges, user_has_supervisor_role
from superviseme.utils.thesis_resources import normalize_resource_url, resolve_resource_type
from superviseme.utils.thesis_management import delete_thesis_with_dependencies
from superviseme.utils.thesis_interest import (
    close_interests_after_direct_assignment,
)
from superviseme.utils.thesis_public import (
    normalize_thesis_descriptions,
    parse_bool,
    set_thesis_keywords,
)
from superviseme.models import *
from superviseme import db
from datetime import datetime
from werkzeug.security import generate_password_hash
import time

# Collaborator roles. "viewer" members can read a project but not change it;
# the owner and every other role can edit its content. Only the owner manages collaborators.
COLLABORATOR_ROLES = ("collaborator", "co-investigator", "research-assistant", "advisor", "viewer")
READ_ONLY_ROLES = ("viewer",)

researcher = Blueprint("researcher", __name__)


@researcher.route("/researcher/dashboard")
@login_required
def dashboard():
    """
    This route is for researcher dashboard. It shows research projects
    and optionally supervisor functions if the researcher has supervisor role.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    # Count research projects
    project_counts = {
        "total": ResearchProject.query.filter_by(researcher_id=current_user.id).count(),
    }

    # Get all research projects for this researcher
    research_projects = ResearchProject.query.filter_by(researcher_id=current_user.id).all()

    # Check if user has supervisor privileges
    has_supervisor_role = user_has_supervisor_role(current_user)

    pending_invitations = (
        ResearchProject_Collaborator.query.filter_by(collaborator_id=current_user.id, status="pending")
        .order_by(ResearchProject_Collaborator.added_at.desc()).all()
    )

    # If user has supervisor role, get supervisor data too
    supervised_thesis_count = 0
    if has_supervisor_role:
        supervised_thesis_count = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).count()

    return render_template(
        "researcher/researcher_dashboard.html",
        current_user=current_user,
        project_counts=project_counts,
        research_projects=research_projects,
        pending_invitations=pending_invitations,
        has_supervisor_role=has_supervisor_role,
        supervised_thesis_count=supervised_thesis_count,
        greeting=__import__("superviseme.utils.dashboard_data", fromlist=["greeting_key"]).greeting_key(),
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


def _project_form_context(exclude=None):
    from superviseme.utils import projects as pj
    mine = [p for p in pj.accessible_projects(current_user) if p.id != getattr(exclude, "id", None)]
    if exclude is not None:
        blocked = pj.descendants_ids(exclude)
        mine = [p for p in mine if p.id not in blocked]
    areas = sorted({p.area for p in pj.accessible_projects(current_user) if p.area})
    return {"project_levels": pj.PROJECT_LEVELS, "parent_options": mine, "known_areas": areas,
            "link_relations": pj.LINK_RELATIONS, "level_label": pj.level_label}


@researcher.route("/researcher/supervisor/dashboard")
@login_required
def supervisor_dashboard():
    """
    Supervisor dashboard functionality within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    from superviseme.utils.dashboard_data import supervisor_overview
    return render_template(
        "researcher/supervisor_dashboard.html",
        current_user=current_user,
        ov=supervisor_overview(current_user),
        has_supervisor_role=True,
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


# First supervisor_theses function removed - duplicate will be kept


@researcher.route("/researcher/supervisor/students")
@login_required
def supervisor_students():
    """
    Student management within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    # Get students supervised by this researcher with their thesis assignments
    supervised_students_query = db.session.execute(
        select(User_mgmt, Thesis)
        .join(Thesis, Thesis.author_id == User_mgmt.id)
        .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)
        .where(Thesis_Supervisor.supervisor_id == current_user.id)
        .where(User_mgmt.user_type == "student")
    ).all()
    
    # Create supervisee info objects that match the template expectations
    def create_supervisee_info(student, thesis):
        class SuperviseeInfo:
            def __init__(self, student, thesis):
                self.student = student
                self.thesis = thesis

                # Activity tracking
                # A student is considered inactive if they haven't been active for more than 2 weeks (14 days)
                cutoff_time = int(time.time()) - (14 * 24 * 60 * 60)

                self.is_inactive = (
                    student.last_activity is None or
                    student.last_activity < cutoff_time
                )

                if student.last_activity:
                    self.days_inactive = (int(time.time()) - student.last_activity) // (24 * 60 * 60)
                else:
                    self.days_inactive = "Unknown"

                self.last_activity_location = student.last_activity_location or "Unknown"
        
        return SuperviseeInfo(student, thesis)
    
    # Create supervisee info objects
    supervisees = []
    past_supervisees = []
    
    for student, thesis in supervised_students_query:
        supervisee_info = create_supervisee_info(student, thesis)
        
        # Check if thesis is frozen/archived
        if thesis.frozen:
            past_supervisees.append(supervisee_info)
        else:
            supervisees.append(supervisee_info)

    return render_template(
        "researcher/supervisor_students.html",
        current_user=current_user,
        supervisees=supervisees,
        past_supervisees=past_supervisees,
        has_supervisor_role=True,
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


@researcher.route("/researcher/supervisor/theses")
@login_required
def supervisor_theses():
    """
    Supervised theses management within researcher context - Enhanced with full CRUD
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    # Get theses supervised by this researcher
    from superviseme.utils.thesis_board import board_context, supervised_scope
    board = board_context(supervised_scope(current_user.id))

    # Get all available students for assignment dropdown (students without active thesis assignments)
    available_students = User_mgmt.query.filter(
        User_mgmt.user_type == "student",
        ~User_mgmt.id.in_(
            db.session.query(Thesis.author_id).filter(Thesis.author_id.isnot(None))
        )
    ).all()

    return render_template(
        "researcher/supervisor_theses.html",
        current_user=current_user,
        **board,
        available_students=available_students,
        has_supervisor_role=True,
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


@researcher.route("/researcher/supervisor/theses/cards")
@login_required
def supervisor_theses_cards():
    """One page of thesis cards (JSON), filtered and paginated server-side."""
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    if not user_has_supervisor_role(current_user):
        abort(403)
    from superviseme.utils.thesis_board import board_response, supervised_scope
    return board_response(supervised_scope(current_user.id), request, "researcher.supervisor_thesis_detail")


@researcher.route("/researcher/supervisor/thesis/<thesis_id>")
@login_required
def supervisor_thesis_detail(thesis_id):
    """
    Thesis detail view within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    # Verify supervisor relationship
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, 
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("You don't have permission to view this thesis")
        return redirect(url_for("researcher.supervisor_theses"))

    thesis = Thesis.query.get_or_404(thesis_id)
    
    # Get student if assigned
    student = None
    if thesis.author_id:
        student = db.session.get(User_mgmt, thesis.author_id)
    
    # Get thesis updates, todos, resources, etc.
    updates = Thesis_Update.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Update.created_at.desc()).all()
    todos = Todo.query.filter_by(thesis_id=thesis_id).order_by(Todo.created_at.desc()).all()
    resources = Resource.query.filter_by(thesis_id=thesis_id).all()
    objectives = Thesis_Objective.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Objective.created_at.desc()).all()
    hypotheses = Thesis_Hypothesis.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Hypothesis.created_at.desc()).all()
    
    # Get supervisors and tags
    supervisors = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).all()
    thesis_tags = Thesis_Tag.query.filter_by(thesis_id=thesis_id).all()
    interests = Thesis_Interest.query.filter_by(thesis_id=thesis_id, status="pending").order_by(
        Thesis_Interest.created_at.desc()
    ).all()
    
    # Get available students for assignment (only students without active thesis assignments)
    available_students = User_mgmt.query.filter(
        User_mgmt.user_type == "student",
        ~User_mgmt.id.in_(
            db.session.query(Thesis.author_id).filter(Thesis.author_id.isnot(None))
        )
    ).all()
    
    # Get meeting notes for this thesis
    meeting_notes = MeetingNote.query.filter_by(thesis_id=thesis_id).order_by(MeetingNote.created_at.desc()).all()

    return render_template(
        "researcher/supervisor_thesis_detail.html",
        current_user=current_user,
        thesis=thesis,
        student=student,
        updates=updates,
        todos=todos,
        resources=resources,
        objectives=objectives,
        hypotheses=hypotheses,
        supervisors=supervisors,
        thesis_tags=thesis_tags,
        interests=interests,
        available_students=available_students,
        meeting_notes=meeting_notes,
        has_supervisor_role=True,
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


@researcher.route("/researcher/supervisor/tag_update", methods=["POST"])
@login_required
def tag_update():
    """
    This route handles tagging an update. It retrieves the necessary data from the form,
    updates the update with the new tags, and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    update_id = request.form.get("update_id")
    tags = request.form.get("tags")
    
    # Verify the update belongs to a thesis supervised by the current user
    update = Thesis_Update.query.join(Thesis, Thesis.id == Thesis_Update.thesis_id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        Thesis_Update.id == update_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if update:
        if tags:
            for tag in tags.split(','):
                tag = tag.strip()
                if tag:
                    existing_tag = Update_Tag.query.filter_by(update_id=update_id, tag=tag).first()
                    if not existing_tag:
                        new_tag = Update_Tag(
                            update_id=update_id,
                            tag=tag
                        )
                        db.session.add(new_tag)
        
        db.session.commit()
        flash("Tags added successfully")
        return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=update.thesis_id))
    
    flash("Update not found or you don't have permission to tag it")
    return redirect(url_for('researcher.supervisor_theses'))


@researcher.route("/researcher/supervisor/toggle_todo/<int:todo_id>", methods=["POST"])
@login_required
def supervisor_toggle_todo(todo_id):
    """
    Toggle todo completion status in researcher-supervisor context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    todo = Todo.query.join(Thesis, Todo.thesis_id == Thesis.id).join(
        Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id
    ).filter(
        Todo.id == todo_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()

    if todo:
        if todo.status == "pending":
            todo.status = "completed"
            todo.completed_at = int(time.time())
        else:
            todo.status = "pending"
            todo.completed_at = None
        todo.updated_at = int(time.time())
        db.session.commit()
        flash("Todo status updated")
    else:
        flash("Todo not found or not accessible")

    return redirect(request.referrer or url_for("researcher.supervisor_dashboard"))


@researcher.route("/researcher/supervisor/delete_todo/<int:todo_id>", methods=["POST"])
@login_required
def supervisor_delete_todo(todo_id):
    """
    Delete todo in researcher-supervisor context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    todo = Todo.query.join(Thesis, Todo.thesis_id == Thesis.id).join(
        Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id
    ).filter(
        Todo.id == todo_id,
        or_(Todo.author_id == current_user.id, Thesis_Supervisor.supervisor_id == current_user.id)
    ).first()

    if todo:
        db.session.delete(todo)
        db.session.commit()
        flash("Todo deleted successfully")
    else:
        flash("Todo not found or not accessible")

    return redirect(request.referrer or url_for("researcher.supervisor_dashboard"))


@researcher.route("/researcher/supervisor/create_thesis", methods=["POST"])
@login_required
def create_thesis():
    """
    Create new thesis within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    title = request.form.get("title")
    description = request.form.get("description")
    short_description = request.form.get("short_description")
    long_description = request.form.get("long_description")
    topic = request.form.get("topic")
    prerequisites = request.form.get("prerequisites")
    is_public = parse_bool(request.form.get("is_public"))
    keywords = request.form.get("keywords")
    level = request.form.get("level")
    student_id = request.form.get("student_id")

    if not title or not description:
        flash("Title and description are required")
        return redirect(url_for("researcher.supervisor_theses"))

    try:
        normalized_short, normalized_long, normalized_description = normalize_thesis_descriptions(
            short_description=short_description,
            long_description=long_description,
            fallback_description=description,
        )

        # Create thesis
        new_thesis = Thesis(
            title=title,
            description=normalized_description,
            short_description=normalized_short,
            long_description=normalized_long,
            topic=(topic or "").strip() or None,
            prerequisites=(prerequisites or "").strip() or None,
            is_public=is_public,
            publisher_id=current_user.id,
            author_id=int(student_id) if student_id and student_id != "" else None,
            frozen=False,
            level=level,
            created_at=int(time.time()),
        )
        db.session.add(new_thesis)
        db.session.flush()
        set_thesis_keywords(db, Thesis_Tag, new_thesis.id, keywords)
        db.session.commit()

        # Assign supervisor
        thesis_supervisor = Thesis_Supervisor(
            thesis_id=new_thesis.id,
            supervisor_id=current_user.id,
            assigned_at=int(time.time()),
        )
        db.session.add(thesis_supervisor)

        # Set initial status
        thesis_status = Thesis_Status(
            thesis_id=new_thesis.id,
            status="thesis accepted",
            updated_at=int(time.time()),
        )
        db.session.add(thesis_status)
        db.session.commit()

        flash("Thesis created successfully")
    except Exception as e:
        flash(f"Error creating thesis: {e}")
    
    return redirect(url_for("researcher.supervisor_theses"))


@researcher.route("/researcher/supervisor/update_thesis", methods=["POST"])
@login_required
def update_thesis():
    """
    Update thesis within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

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

    # Verify supervisor relationship
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, 
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("You don't have permission to update this thesis")
        return redirect(url_for("researcher.supervisor_theses"))

    try:
        thesis = db.session.get(Thesis, thesis_id)
        if thesis:
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
    except Exception as e:
        flash(f"Error updating thesis: {e}")
    
    return redirect(url_for("researcher.supervisor_theses"))


@researcher.route("/researcher/supervisor/delete_thesis/<int:thesis_id>", methods=["POST", "DELETE"])
@login_required
def delete_thesis(thesis_id):
    """
    Delete thesis within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    # Verify supervisor relationship
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, 
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("You don't have permission to delete this thesis")
        return redirect(url_for("researcher.supervisor_theses"))

    success, error = delete_thesis_with_dependencies(thesis_id)
    if not success:
        if request.method == "DELETE":
            return jsonify({"status": "error", "message": error or "Unable to delete thesis"}), 400
        flash(f"Error deleting thesis: {error}")
        return redirect(url_for("researcher.supervisor_theses"))

    db.session.commit()
    if request.method == "DELETE":
        return jsonify({"status": "success"}), 200

    flash("Thesis deleted successfully")
    return redirect(url_for("researcher.supervisor_theses"))


@researcher.route("/researcher/supervisor/create_student", methods=["POST"])
@login_required
def create_student():
    """
    Create new student within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    username = request.form.get("username")
    name = request.form.get("name")
    surname = request.form.get("surname")
    email = request.form.get("email")
    password = request.form.get("password")
    cdl = request.form.get("cdl")
    gender = request.form.get("gender")
    nationality = request.form.get("nationality")

    if not all([username, name, surname, email, password]):
        flash("All required fields must be filled")
        return redirect(url_for("researcher.supervisor_students"))

    pw_error = security.validate_password(password)
    if pw_error:
        flash(pw_error)
        return redirect(url_for("researcher.supervisor_students"))

    # Check if username or email already exists
    existing_user = User_mgmt.query.filter(
        or_(User_mgmt.username == username, User_mgmt.email == email)
    ).first()
    
    if existing_user:
        flash("Username or email already exists")
        return redirect(url_for("researcher.supervisor_students"))

    try:
        # Create student
        new_student = User_mgmt(
            username=username,
            name=name,
            surname=surname,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            user_type="student",
            cdl=cdl,
            gender=gender,
            nationality=nationality,
            joined_on=int(time.time())
        )
        db.session.add(new_student)
        db.session.commit()
        flash("Student created successfully")
    except Exception as e:
        flash(f"Error creating student: {e}")
    
    return redirect(url_for("researcher.supervisor_students"))


@researcher.route("/researcher/supervisor/edit_student/<int:student_id>", methods=["POST"])
@login_required
def edit_student(student_id):
    """
    Edit student within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    student = User_mgmt.query.get_or_404(student_id)
    
    # Check if this student is supervised by current user
    supervised_relationship = db.session.execute(
        select(Thesis_Supervisor)
        .join(Thesis, Thesis.id == Thesis_Supervisor.thesis_id)
        .where(Thesis.author_id == student_id)
        .where(Thesis_Supervisor.supervisor_id == current_user.id)
    ).first()
    
    if not supervised_relationship:
        flash("You don't have permission to edit this student")
        return redirect(url_for("researcher.supervisor_students"))

    try:
        student.name = request.form.get("name", student.name)
        student.surname = request.form.get("surname", student.surname)
        student.email = request.form.get("email", student.email)
        student.cdl = request.form.get("cdl", student.cdl)
        student.gender = request.form.get("gender", student.gender)
        student.nationality = request.form.get("nationality", student.nationality)
        
        # Update password if provided
        new_password = request.form.get("password")
        if new_password:
            pw_error = security.validate_password(new_password)
            if pw_error:
                flash(pw_error)
                return redirect(url_for("researcher.supervisor_students"))
            student.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        db.session.commit()
        flash("Student updated successfully")
    except Exception as e:
        flash(f"Error updating student: {e}")
    
    return redirect(url_for("researcher.supervisor_students"))


@researcher.route("/researcher/supervisor/delete_student/<int:student_id>", methods=["POST", "DELETE"])
@login_required
def delete_student(student_id):
    """
    Delete student within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    student = User_mgmt.query.get_or_404(student_id)
    
    # Check if this student is supervised by current user
    supervised_relationship = db.session.execute(
        select(Thesis_Supervisor)
        .join(Thesis, Thesis.id == Thesis_Supervisor.thesis_id)
        .where(Thesis.author_id == student_id)
        .where(Thesis_Supervisor.supervisor_id == current_user.id)
    ).first()
    
    if not supervised_relationship:
        flash("You don't have permission to delete this student")
        return redirect(url_for("researcher.supervisor_students"))

    try:
        theses = Thesis.query.filter_by(author_id=student_id).all()
        for thesis in theses:
            success, error = delete_thesis_with_dependencies(thesis.id)
            if not success:
                flash(f"Error deleting thesis '{thesis.title}': {error}")
                return redirect(url_for("researcher.supervisor_students"))

        db.session.delete(student)
        db.session.commit()
        flash("Student and associated data deleted successfully")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting student: {e}")
    
    return redirect(url_for("researcher.supervisor_students"))


@researcher.route("/researcher/supervisor/assign_thesis", methods=["POST"])
@login_required
def assign_thesis():
    """
    Assign thesis to student within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    thesis_id = request.form.get("thesis_id")
    student_id = request.form.get("student_id")

    # Verify supervisor relationship with thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, 
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("You don't have permission to assign this thesis")
        return redirect(url_for("researcher.supervisor_theses"))

    try:
        thesis = db.session.get(Thesis, thesis_id)
        if thesis and student_id and not thesis.author_id:
            from superviseme.utils.capacity import active_thesis_message, capacity_message
            over = active_thesis_message(int(student_id), thesis.id) or capacity_message(thesis)
            if over:
                flash(over, "warning")
                return redirect(url_for("researcher.supervisor_theses"))
        if thesis:
            thesis.author_id = int(student_id) if student_id else None
            if thesis.author_id:
                close_interests_after_direct_assignment(
                    thesis_id=thesis.id,
                    assigned_student_id=thesis.author_id,
                    handler_id=current_user.id,
                )
            db.session.commit()
            flash("Thesis assigned successfully")
    except Exception as e:
        flash(f"Error assigning thesis: {e}")
    
    return redirect(url_for("researcher.supervisor_theses"))


@researcher.route("/researcher/supervisor/unassign_thesis/<int:thesis_id>", methods=["POST"])
@login_required
def unassign_thesis(thesis_id):
    """
    Unassign thesis from student within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    # Verify supervisor relationship
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, 
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("You don't have permission to unassign this thesis")
        return redirect(url_for("researcher.supervisor_theses"))

    try:
        thesis = db.session.get(Thesis, thesis_id)
        if thesis:
            thesis.author_id = None
            db.session.commit()
            flash("Thesis unassigned successfully")
    except Exception as e:
        flash(f"Error unassigning thesis: {e}")
    
    return redirect(url_for("researcher.supervisor_theses"))


@researcher.route("/researcher/supervisor/todo/<int:todo_id>")
@login_required
def supervisor_todo_detail(todo_id):
    """
    Display todo detail with linked updates and references within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if researcher has supervisor privileges
    supervisor_role = Supervisor_Role.query.filter_by(
        researcher_id=current_user.id, active=True
    ).first()
    if not supervisor_role:
        flash("You need supervisor privileges to access this feature.")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify supervisor has access to this todo
    todo = Todo.query.join(Thesis, Todo.thesis_id == Thesis.id)\
                    .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)\
                    .filter(Todo.id == todo_id, Thesis_Supervisor.supervisor_id == current_user.id)\
                    .first()
    
    if not todo:
        flash("Todo not found or you don't have permission to view it.")
        return redirect(url_for("researcher.supervisor_dashboard"))
    
    # Get referenced updates
    from superviseme.models import Todo_Reference
    referenced_updates = db.session.query(Thesis_Update).join(Todo_Reference).filter(
        Todo_Reference.todo_id == todo_id
    ).order_by(Thesis_Update.created_at.desc()).all()
    
    return render_template("researcher/supervisor_todo_detail.html", todo=todo, 
                           referenced_updates=referenced_updates, 
                           dt=datetime.fromtimestamp)


@researcher.route("/researcher/supervisor/meeting_note/<int:note_id>")
@login_required
def supervisor_meeting_note_detail(note_id):
    """
    Display detailed view of a meeting note with full CRUD capabilities within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if researcher has supervisor privileges
    supervisor_role = Supervisor_Role.query.filter_by(
        researcher_id=current_user.id, active=True
    ).first()
    if not supervisor_role:
        flash("You need supervisor privileges to access this feature.")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify supervisor has access to this meeting note
    meeting_note = MeetingNote.query.join(Thesis, MeetingNote.thesis_id == Thesis.id)\
                                   .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)\
                                   .filter(MeetingNote.id == note_id, Thesis_Supervisor.supervisor_id == current_user.id)\
                                   .first()
    
    if not meeting_note:
        flash("Meeting note not found or you don't have permission to view it.")
        return redirect(url_for("researcher.supervisor_dashboard"))
    
    thesis = meeting_note.thesis
    
    # Get todos for this thesis for reference dropdown
    todos = Todo.query.filter_by(thesis_id=thesis.id).order_by(Todo.created_at.desc()).all()
    
    # Get existing references for this meeting note
    references = MeetingNoteReference.query.filter_by(meeting_note_id=note_id).all()
    
    return render_template("researcher/supervisor_meeting_note_detail.html", 
                         meeting_note=meeting_note, 
                         thesis=thesis,
                         todos=todos,
                         references=references,
                         dt=datetime.fromtimestamp)


@researcher.route("/researcher/supervisor/add_meeting_note_reference", methods=["POST"])
@login_required
def add_meeting_note_reference():
    """
    Add a todo reference to a meeting note within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    note_id = request.form.get("note_id") or request.view_args.get("note_id")
    todo_id = request.form.get("todo_id")
    
    if not note_id or not todo_id:
        flash("Missing required parameters")
        return redirect(url_for("researcher.supervisor_theses"))
    
    # Verify supervisor has access to this meeting note
    meeting_note = MeetingNote.query.join(Thesis, MeetingNote.thesis_id == Thesis.id)\
                                   .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)\
                                   .filter(MeetingNote.id == note_id, 
                                          Thesis_Supervisor.supervisor_id == current_user.id)\
                                   .first()
    
    if not meeting_note:
        flash("Meeting note not found or you don't have permission to modify it")
        return redirect(url_for("researcher.supervisor_theses"))
    
    # Verify the todo belongs to the same thesis
    todo = Todo.query.filter_by(id=todo_id, thesis_id=meeting_note.thesis_id).first()
    if not todo:
        flash("Todo not found or doesn't belong to this thesis")
        return redirect(url_for("researcher.supervisor_meeting_note_detail", note_id=note_id))
    
    # Check if reference already exists
    existing_ref = MeetingNoteReference.query.filter_by(
        meeting_note_id=note_id, 
        todo_id=todo_id
    ).first()
    
    if existing_ref:
        flash("This todo is already referenced in this meeting note")
    else:
        # Create new reference
        new_reference = MeetingNoteReference(
            meeting_note_id=note_id,
            todo_id=todo_id,
            created_at=int(time.time())
        )
        db.session.add(new_reference)
        db.session.commit()
        flash("Todo reference added successfully")
    
    return redirect(url_for("researcher.supervisor_meeting_note_detail", note_id=note_id))


@researcher.route("/researcher/supervisor/remove_meeting_note_reference/<int:note_id>/<int:reference_id>", methods=["POST"])
@login_required
def remove_meeting_note_reference(note_id, reference_id):
    """
    Remove a todo reference from a meeting note within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify supervisor has access to this meeting note
    meeting_note = MeetingNote.query.join(Thesis, MeetingNote.thesis_id == Thesis.id)\
                                   .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)\
                                   .filter(MeetingNote.id == note_id, 
                                          Thesis_Supervisor.supervisor_id == current_user.id)\
                                   .first()
    
    if not meeting_note:
        flash("Meeting note not found or you don't have permission to modify it")
        return redirect(url_for("researcher.supervisor_theses"))
    
    # Find and remove the reference
    reference = MeetingNoteReference.query.filter_by(
        id=reference_id, 
        meeting_note_id=note_id
    ).first()
    
    if reference:
        db.session.delete(reference)
        db.session.commit()
        flash("Todo reference removed successfully")
    else:
        flash("Reference not found")
    
    return redirect(url_for("researcher.supervisor_meeting_note_detail", note_id=note_id))


@researcher.route("/researcher/supervisor/search", methods=["POST"])
@login_required
def supervisor_search():
    """
    Handle searching for theses or supervisees within researcher context
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if researcher has supervisor privileges
    supervisor_role = Supervisor_Role.query.filter_by(
        researcher_id=current_user.id, active=True
    ).first()
    if not supervisor_role:
        flash("You need supervisor privileges to access this feature.")
        return redirect(url_for("researcher.dashboard"))
    
    search_term = request.form.get("search_term", "").strip()

    # Validate search term
    if not search_term:
        flash("Please enter a search term.", "warning")
        return redirect(url_for('researcher.supervisor_dashboard'))

    # Search for theses supervised by current user
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    supervised_thesis_ids = [ts.thesis_id for ts in thesis_supervisors]
    
    theses = []
    supervisees = []
    
    if search_term:
        # Search for supervised theses
        theses = Thesis.query.filter(
            and_(
                Thesis.id.in_(supervised_thesis_ids),
                or_(
                    Thesis.title.ilike(f"%{search_term}%"),
                    Thesis.description.ilike(f"%{search_term}%"),
                    Thesis.level.ilike(f"%{search_term}%")
                )
            )
        ).all()

        # Search for supervisees (students with supervised theses)
        supervised_student_ids = [thesis.author_id for thesis in Thesis.query.filter(Thesis.id.in_(supervised_thesis_ids)).all() if thesis.author_id]
        supervisees = User_mgmt.query.filter(
            and_(
                User_mgmt.id.in_(supervised_student_ids),
                or_(
                    User_mgmt.name.ilike(f"%{search_term}%"),
                    User_mgmt.surname.ilike(f"%{search_term}%"),
                    User_mgmt.username.ilike(f"%{search_term}%"),
                    User_mgmt.email.ilike(f"%{search_term}%")
                )
            )
        ).all()

    return render_template("researcher/supervisor_search_results.html", 
                         theses=theses, 
                         supervisees=supervisees,
                         search_term=search_term,
                         user_type="researcher")


# ============================================================================
# RESEARCH PROJECT ADVANCED FEATURES - STATUS, UPDATES, TODOS, RESOURCES, ETC.
# ============================================================================

# Missing route: delete_project_resource
# Missing routes: freeze_thesis and unfreeze_thesis
@researcher.route("/researcher/freeze_thesis", methods=["POST"])
@login_required
def freeze_thesis():
    """
    Freeze a thesis (researcher acting as supervisor)
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    thesis_id = request.form.get("thesis_id")
    if not thesis_id:
        flash("Thesis ID is required")
        return redirect(url_for("researcher.supervisor_theses"))

    # Verify supervisor relationship with thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, 
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("You don't have permission to freeze this thesis")
        return redirect(url_for("researcher.supervisor_theses"))

    try:
        thesis = db.session.get(Thesis, thesis_id)
        if thesis:
            thesis.frozen = True
            db.session.commit()
            flash("Thesis frozen successfully")
    except Exception as e:
        flash(f"Error freezing thesis: {e}")
    
    return redirect(url_for("researcher.supervisor_theses"))


@researcher.route("/researcher/unfreeze_thesis", methods=["POST"])
@login_required
def unfreeze_thesis():
    """
    Unfreeze a thesis (researcher acting as supervisor)
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))

    thesis_id = request.form.get("thesis_id")
    if not thesis_id:
        flash("Thesis ID is required")
        return redirect(url_for("researcher.supervisor_theses"))

    # Verify supervisor relationship with thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id, 
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("You don't have permission to unfreeze this thesis")
        return redirect(url_for("researcher.supervisor_theses"))

    try:
        thesis = db.session.get(Thesis, thesis_id)
        if thesis:
            thesis.frozen = False
            db.session.commit()
            flash("Thesis unfrozen successfully")
    except Exception as e:
        flash(f"Error unfreezing thesis: {e}")
    
    return redirect(url_for("researcher.supervisor_theses"))


# Additional CRUD operations for project resources
# CRUD operations for project todos
# CRUD operations for project objectives
# CRUD operations for project hypotheses
# CRUD operations for project meeting notes
# CRUD operations for project updates
# ==============================================================================
# DETAIL ROUTES WITH CRUD FUNCTIONALITY FOR MEETING NOTES, TODOS, AND UPDATES
# ==============================================================================

# Missing routes for template compatibility
@researcher.route("/researcher/supervisor/freeze_objective/<int:objective_id>", methods=["POST"])
@login_required
def supervisor_freeze_objective(objective_id):
    """Freeze an objective"""
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify supervisor has access to this objective
    objective = Thesis_Objective.query.join(
        Thesis_Supervisor, Thesis_Objective.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Thesis_Objective.id == objective_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not objective:
        flash("Objective not found or not accessible")
        return redirect(url_for('researcher.supervisor_theses'))
    
    objective.frozen = True
    db.session.commit()
    flash("Objective frozen successfully")
    
    return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=objective.thesis_id))


@researcher.route("/researcher/supervisor/unfreeze_objective/<int:objective_id>", methods=["POST"])
@login_required
def supervisor_unfreeze_objective(objective_id):
    """Unfreeze an objective"""
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify supervisor has access to this objective
    objective = Thesis_Objective.query.join(
        Thesis_Supervisor, Thesis_Objective.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Thesis_Objective.id == objective_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not objective:
        flash("Objective not found or not accessible")
        return redirect(url_for('researcher.supervisor_theses'))
    
    objective.frozen = False
    db.session.commit()
    flash("Objective unfrozen successfully")
    
    return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=objective.thesis_id))


@researcher.route("/researcher/supervisor/freeze_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def supervisor_freeze_hypothesis(hypothesis_id):
    """Freeze a hypothesis"""
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify supervisor has access to this hypothesis
    hypothesis = Thesis_Hypothesis.query.join(
        Thesis_Supervisor, Thesis_Hypothesis.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Thesis_Hypothesis.id == hypothesis_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not hypothesis:
        flash("Hypothesis not found or not accessible")
        return redirect(url_for('researcher.supervisor_theses'))
    
    hypothesis.frozen = True
    db.session.commit()
    flash("Hypothesis frozen successfully")
    
    return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=hypothesis.thesis_id))


@researcher.route("/researcher/supervisor/unfreeze_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def supervisor_unfreeze_hypothesis(hypothesis_id):
    """Unfreeze a hypothesis"""
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify supervisor has access to this hypothesis
    hypothesis = Thesis_Hypothesis.query.join(
        Thesis_Supervisor, Thesis_Hypothesis.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Thesis_Hypothesis.id == hypothesis_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not hypothesis:
        flash("Hypothesis not found or not accessible")
        return redirect(url_for('researcher.supervisor_theses'))
    
    hypothesis.frozen = False
    db.session.commit()
    flash("Hypothesis unfrozen successfully")
    
    return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=hypothesis.thesis_id))


@researcher.route("/researcher/supervisor/add_resource", methods=["POST"])
@login_required
def supervisor_add_resource():
    """Add a resource to a supervised thesis"""
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    thesis_id = request.form.get("thesis_id")
    resource_type = request.form.get("resource_type")
    resource_url = request.form.get("resource_url")
    description = request.form.get("description", "")
    
    # Verify supervisor has access to this thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("Thesis not found or not supervised by you")
        return redirect(url_for('researcher.supervisor_theses'))
    
    resource_url = normalize_resource_url(resource_url)
    if not resource_url:
        flash("Please provide a valid http(s) link.")
        return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=thesis_id))
    resource_type = resolve_resource_type(resource_type, resource_url)

    new_resource = Resource(
        thesis_id=thesis_id,
        resource_type=resource_type,
        resource_url=resource_url,
        description=description,
        created_at=int(time.time())
    )
    
    db.session.add(new_resource)
    db.session.commit()
    flash("Resource added successfully")
    
    return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=thesis_id))


@researcher.route("/researcher/supervisor/delete_update/<int:update_id>", methods=["POST", "DELETE"])
@login_required
def supervisor_delete_update(update_id):
    """Delete a supervisor update"""
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify the update belongs to a thesis supervised by the current user
    update = Thesis_Update.query.join(Thesis_Supervisor).filter(
        Thesis_Update.id == update_id,
        Thesis_Update.update_type == "supervisor_update",
        Thesis_Update.author_id == current_user.id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if update:
        thesis_id = update.thesis_id
        db.session.delete(update)
        db.session.commit()
        flash("Update deleted successfully")
        return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=thesis_id))
    
    flash("Update not found or you don't have permission to delete it")
    return redirect(url_for('researcher.supervisor_theses'))


@researcher.route("/researcher/supervisor/delete_resource/<int:resource_id>", methods=["POST", "DELETE"])
@login_required
def supervisor_delete_resource(resource_id):
    """Delete a thesis resource"""
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    
    # Check if user has supervisor privileges
    if not user_has_supervisor_role(current_user):
        flash("You don't have supervisor privileges")
        return redirect(url_for("researcher.dashboard"))
    
    # Verify supervisor has access to this resource through thesis supervision
    resource = Resource.query.join(Thesis_Supervisor, Resource.thesis_id == Thesis_Supervisor.thesis_id).filter(
        Resource.id == resource_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not resource:
        flash("Resource not found or not accessible")
        return redirect(url_for('researcher.supervisor_theses'))
    
    thesis_id = resource.thesis_id
    db.session.delete(resource)
    db.session.commit()
    flash("Resource deleted successfully")
    
    return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=thesis_id))


# --- Thesis presentation: images and external reference links -----------------

# --- Project presentation: images, links, structured report -------------------------------------------------

def _owned_project_or_404(project_id):
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return None, privilege_check
    project = ResearchProject.query.get_or_404(project_id)
    if project.researcher_id != current_user.id:
        abort(403)
    return project, None


from superviseme.routes import researcher_projects  # noqa: E402,F401  (registers the project routes)
from superviseme.routes import researcher_output  # noqa: E402,F401  (registers research-output and portfolio routes)


# ---------------------------------------------------------------------------
# Supervision actions shared with the supervisor blueprint. Researchers with the supervisor role
# use the very same view functions (they adapt to the blueprint that serves them, see
# superviseme/routes/_supervision.py); only the URLs and endpoint names are researcher-specific.
# ---------------------------------------------------------------------------
from superviseme.routes import supervisor as _supervisor_views  # noqa: E402

_SHARED_SUPERVISION_ROUTES = [
    ("/researcher/supervisor/post_update", "post_update", ["POST"]),
    ("/researcher/supervisor/modify_update", "modify_update", ["POST"]),
    ("/researcher/supervisor/comment_on_update", "comment_on_update", ["POST"]),
    ("/researcher/supervisor/set_thesis_status", "set_thesis_status", ["POST"]),
    ("/researcher/supervisor/add_todo", "add_todo", ["POST"]),
    ("/researcher/supervisor/add_meeting_note", "add_meeting_note", ["POST"]),
    ("/researcher/supervisor/edit_meeting_note/<int:note_id>", "edit_meeting_note", ["POST"]),
    ("/researcher/supervisor/delete_meeting_note/<int:note_id>", "delete_meeting_note", ["POST", "DELETE"]),
    ("/researcher/supervisor/add_objective", "add_objective", ["POST"]),
    ("/researcher/supervisor/edit_objective/<int:objective_id>", "edit_objective", ["POST"]),
    ("/researcher/supervisor/delete_objective/<int:objective_id>", "delete_objective", ["POST", "DELETE"]),
    ("/researcher/supervisor/add_hypothesis", "add_hypothesis", ["POST"]),
    ("/researcher/supervisor/edit_hypothesis/<int:hypothesis_id>", "edit_hypothesis", ["POST"]),
    ("/researcher/supervisor/delete_hypothesis/<int:hypothesis_id>", "delete_hypothesis", ["POST", "DELETE"]),
    ("/researcher/supervisor/thesis_interest/assign/<int:interest_id>", "assign_thesis_interest", ["POST"]),
    ("/researcher/supervisor/thesis_interest/delete/<int:interest_id>", "delete_thesis_interest", ["POST"]),
    ("/researcher/supervisor/thesis/<int:thesis_id>/images", "add_thesis_images", ["POST"]),
    ("/researcher/supervisor/thesis/<int:thesis_id>/images/<int:image_id>/delete", "delete_thesis_image", ["POST"]),
    ("/researcher/supervisor/thesis/<int:thesis_id>/links", "add_thesis_link", ["POST"]),
    ("/researcher/supervisor/thesis/<int:thesis_id>/links/<int:link_id>/delete", "delete_thesis_link", ["POST"]),
]
for _rule, _name, _methods in _SHARED_SUPERVISION_ROUTES:
    researcher.add_url_rule(_rule, endpoint=_name, view_func=getattr(_supervisor_views, _name), methods=_methods)
