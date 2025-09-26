from flask import Blueprint, request, render_template, abort, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from sqlalchemy import select, and_, func, or_
from superviseme.utils.miscellanea import check_privileges, user_has_supervisor_role
from superviseme.models import *
from superviseme import db
from datetime import datetime
from werkzeug.security import generate_password_hash
import time

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

    # If user has supervisor role, get supervisor data too
    supervised_thesis_count = 0
    if has_supervisor_role:
        supervised_thesis_count = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).count()

    return render_template(
        "researcher/researcher_dashboard.html",
        current_user=current_user,
        project_counts=project_counts,
        research_projects=research_projects,
        has_supervisor_role=has_supervisor_role,
        supervised_thesis_count=supervised_thesis_count,
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


@researcher.route("/researcher/projects")
@login_required
def projects():
    """
    This route displays all research projects for the current researcher.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    # Get all research projects for this researcher
    research_projects = ResearchProject.query.filter_by(researcher_id=current_user.id).all()

    # For each project, get collaborators
    projects_with_collaborators = []
    for project in research_projects:
        collaborators = ResearchProject_Collaborator.query.filter_by(project_id=project.id).all()
        collaborator_users = []
        for collab in collaborators:
            user = User_mgmt.query.get(collab.collaborator_id)
            if user:
                collaborator_users.append({"user": user, "role": collab.role})
        
        projects_with_collaborators.append({
            "project": project,
            "collaborators": collaborator_users
        })

    return render_template(
        "researcher/projects.html",
        current_user=current_user,
        projects_with_collaborators=projects_with_collaborators,
        has_supervisor_role=user_has_supervisor_role(current_user)
    )


@researcher.route("/researcher/create_project", methods=["POST"])
@login_required
def create_project():
    """
    This route handles creating a new research project.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    title = request.form.get("title")
    description = request.form.get("description")
    level = request.form.get("level")

    if not title or not description:
        flash("Title and description are required")
        return redirect(request.referrer)

    try:
        new_project = ResearchProject(
            title=title,
            description=description,
            researcher_id=current_user.id,
            frozen=False,
            level=level,
            created_at=int(time.time()),
        )
        db.session.add(new_project)
        db.session.commit()

        flash("Research project created successfully")
        return redirect(url_for("researcher.projects"))
    except Exception as e:
        flash(f"Error creating research project: {e}")
        return redirect(request.referrer)


@researcher.route("/researcher/update_project", methods=["POST"])
@login_required
def update_project():
    """
    This route handles updating a research project.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project_id = request.form.get("project_id")
    title = request.form.get("title")
    description = request.form.get("description")
    level = request.form.get("level")

    if not project_id:
        flash("Project ID is required")
        return redirect(request.referrer)

    project = ResearchProject.query.get(project_id)
    if not project or project.researcher_id != current_user.id:
        flash("Project not found or access denied")
        return redirect(url_for("researcher.projects"))

    try:
        if title:
            project.title = title
        if description:
            project.description = description
        if level:
            project.level = level

        db.session.commit()
        flash("Project updated successfully")
        return redirect(url_for("researcher.projects"))
    except Exception as e:
        flash(f"Error updating project: {e}")
        return redirect(request.referrer)


@researcher.route("/researcher/delete_project/<int:project_id>", methods=["DELETE"])
@login_required
def delete_project(project_id):
    """
    This route handles deleting a research project.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project or project.researcher_id != current_user.id:
        return jsonify({"status": "error", "message": "Project not found or access denied"}), 404

    try:
        # Remove collaborators first
        ResearchProject_Collaborator.query.filter_by(project_id=project_id).delete()
        
        # Remove the project
        db.session.delete(project)
        db.session.commit()

        return jsonify({"status": "success", "message": "Project deleted successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error deleting project: {e}"}), 500


@researcher.route("/researcher/add_collaborator", methods=["POST"])
@login_required
def add_collaborator():
    """
    This route handles adding a collaborator to a research project.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project_id = request.form.get("project_id")
    collaborator_email = request.form.get("collaborator_email")
    role = request.form.get("role", "collaborator")

    if not project_id or not collaborator_email:
        flash("Project ID and collaborator email are required")
        return redirect(request.referrer)

    project = ResearchProject.query.get(project_id)
    if not project or project.researcher_id != current_user.id:
        flash("Project not found or access denied")
        return redirect(url_for("researcher.projects"))

    # Find the user by email
    collaborator = User_mgmt.query.filter_by(email=collaborator_email).first()
    if not collaborator:
        flash("User with this email not found")
        return redirect(request.referrer)

    # Check if already a collaborator
    existing = ResearchProject_Collaborator.query.filter_by(
        project_id=project_id, collaborator_id=collaborator.id
    ).first()
    if existing:
        flash("User is already a collaborator on this project")
        return redirect(request.referrer)

    try:
        new_collaborator = ResearchProject_Collaborator(
            project_id=project_id,
            collaborator_id=collaborator.id,
            role=role,
            added_at=int(time.time())
        )
        db.session.add(new_collaborator)
        db.session.commit()

        flash(f"Collaborator {collaborator.name} {collaborator.surname} added successfully")
        return redirect(url_for("researcher.projects"))
    except Exception as e:
        flash(f"Error adding collaborator: {e}")
        return redirect(request.referrer)


@researcher.route("/researcher/remove_collaborator", methods=["POST"])
@login_required
def remove_collaborator():
    """
    This route handles removing a collaborator from a research project.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project_id = request.form.get("project_id")
    collaborator_id = request.form.get("collaborator_id")

    if not project_id or not collaborator_id:
        flash("Project ID and collaborator ID are required")
        return redirect(request.referrer)

    project = ResearchProject.query.get(project_id)
    if not project or project.researcher_id != current_user.id:
        flash("Project not found or access denied")
        return redirect(url_for("researcher.projects"))

    try:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=collaborator_id
        ).first()
        
        if collaboration:
            db.session.delete(collaboration)
            db.session.commit()
            flash("Collaborator removed successfully")
        else:
            flash("Collaboration not found")
        
        return redirect(url_for("researcher.projects"))
    except Exception as e:
        flash(f"Error removing collaborator: {e}")
        return redirect(request.referrer)


@researcher.route("/researcher/project/<int:project_id>")
@login_required
def project_detail(project_id):
    """
    This route displays detailed information about a research project with all features.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check if user has access (either owner or collaborator)
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    # Get collaborators
    collaborators = ResearchProject_Collaborator.query.filter_by(project_id=project_id).all()
    collaborator_users = []
    for collab in collaborators:
        user = User_mgmt.query.get(collab.collaborator_id)
        if user:
            collaborator_users.append({"user": user, "role": collab.role})

    # Get project statistics
    updates_count = ResearchProject_Update.query.filter_by(project_id=project_id).count()
    todos_count = ResearchProject_Todo.query.filter_by(project_id=project_id).count()
    completed_todos_count = ResearchProject_Todo.query.filter_by(project_id=project_id, status="completed").count()
    resources_count = ResearchProject_Resource.query.filter_by(project_id=project_id).count()
    objectives_count = ResearchProject_Objective.query.filter_by(project_id=project_id).count()
    hypotheses_count = ResearchProject_Hypothesis.query.filter_by(project_id=project_id).count()
    meeting_notes_count = ResearchProject_MeetingNote.query.filter_by(project_id=project_id).count()

    # Get recent updates (last 5)
    recent_updates = ResearchProject_Update.query.filter_by(project_id=project_id).order_by(ResearchProject_Update.created_at.desc()).limit(5).all()

    # Get recent todos (last 5)
    recent_todos = ResearchProject_Todo.query.filter_by(project_id=project_id).order_by(ResearchProject_Todo.created_at.desc()).limit(5).all()

    # Get current status
    current_status = ResearchProject_Status.query.filter_by(project_id=project_id).order_by(ResearchProject_Status.updated_at.desc()).first()

    return render_template(
        "researcher/project_detail.html",
        current_user=current_user,
        project=project,
        collaborators=collaborator_users,
        has_supervisor_role=user_has_supervisor_role(current_user),
        is_owner=(project.researcher_id == current_user.id),
        updates_count=updates_count,
        todos_count=todos_count,
        completed_todos_count=completed_todos_count,
        resources_count=resources_count,
        objectives_count=objectives_count,
        hypotheses_count=hypotheses_count,
        meeting_notes_count=meeting_notes_count,
        recent_updates=recent_updates,
        recent_todos=recent_todos,
        current_status=current_status,
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


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

    # Get supervisor statistics (replicating supervisor dashboard logic)
    user_counts = {
        "students": db.session.execute(
                    select(func.count())
                    .select_from(User_mgmt)
                    .join(Thesis, Thesis.author_id == User_mgmt.id)
                    .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)
                    .where(Thesis_Supervisor.supervisor_id == current_user.id)
                ).scalar_one()
    }

    # count all theses by their status
    thesis_counts = {
        "total": Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).count(),
    }

    # Get theses for this supervisor
    supervised_theses = db.session.execute(
        select(Thesis, User_mgmt)
        .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)
        .outerjoin(User_mgmt, Thesis.author_id == User_mgmt.id)
        .where(Thesis_Supervisor.supervisor_id == current_user.id)
    ).all()

    return render_template(
        "researcher/supervisor_dashboard.html",
        current_user=current_user,
        user_counts=user_counts,
        thesis_counts=thesis_counts,
        supervised_theses=supervised_theses,
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

    # Get students supervised by this researcher (with and without thesis assignments)
    supervised_students = db.session.execute(
        select(User_mgmt, Thesis)
        .join(Thesis, Thesis.author_id == User_mgmt.id)
        .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)
        .where(Thesis_Supervisor.supervisor_id == current_user.id)
        .where(User_mgmt.user_type == "student")
    ).all()
    
    # Also get students without thesis assignments that were created by this researcher
    # For now, we'll show all students created recently as a temporary solution
    # In a real implementation, you'd want to track who created each student
    unassigned_students = User_mgmt.query.filter_by(user_type="student").all()
    
    # Filter out students who already have thesis assignments
    assigned_student_ids = {student.id for student, thesis in supervised_students}
    unassigned_students = [student for student in unassigned_students if student.id not in assigned_student_ids]
    
    # Combine both lists - create tuples with None for thesis for unassigned students
    all_students = list(supervised_students) + [(student, None) for student in unassigned_students]

    return render_template(
        "researcher/supervisor_students.html",
        current_user=current_user,
        supervised_students=all_students,
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
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    theses = [ts.thesis for ts in thesis_supervisors]

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
        theses=theses,
        available_students=available_students,
        has_supervisor_role=True,
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


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
        student = User_mgmt.query.get(thesis.author_id)
    
    # Get thesis updates, todos, resources, etc.
    updates = Thesis_Update.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Update.created_at.desc()).all()
    todos = Todo.query.filter_by(thesis_id=thesis_id).order_by(Todo.created_at.desc()).all()
    resources = Resource.query.filter_by(thesis_id=thesis_id).all()
    objectives = Thesis_Objective.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Objective.created_at.desc()).all()
    hypotheses = Thesis_Hypothesis.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Hypothesis.created_at.desc()).all()
    
    # Get supervisors and tags
    supervisors = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).all()
    thesis_tags = Thesis_Tag.query.filter_by(thesis_id=thesis_id).all()
    
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
        available_students=available_students,
        meeting_notes=meeting_notes,
        has_supervisor_role=True,
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


@researcher.route("/researcher/supervisor/post_update", methods=["POST"])
@login_required
def post_update():
    """
    This route handles posting updates to a thesis. It retrieves the necessary data from the form,
    creates a new Update object, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    thesis_id = request.form.get("thesis_id")
    content = request.form.get("content")

    # Verify researcher has access to this thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("You don't have permission to update this thesis")
        return redirect(url_for('researcher.supervisor_theses'))

    new_update = Thesis_Update(
        thesis_id=thesis_id,
        author_id=current_user.id,
        content=content,
        update_type="supervisor_update",
        created_at=int(time.time())
    )

    db.session.add(new_update)
    db.session.commit()

    # Parse and create todo references
    from superviseme.utils.todo_parser import parse_todo_references, create_todo_references
    todo_refs = parse_todo_references(content)
    if todo_refs:
        create_todo_references(new_update.id, todo_refs)

    # Create notification for student
    from superviseme.utils.notifications import create_supervisor_feedback_notification
    create_supervisor_feedback_notification(thesis_id, current_user.id, content)

    flash("Update posted successfully")
    return redirect(url_for('researcher.supervisor_thesis_detail', thesis_id=thesis_id))


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
    level = request.form.get("level")
    student_id = request.form.get("student_id")

    if not title or not description:
        flash("Title and description are required")
        return redirect(url_for("researcher.supervisor_theses"))

    try:
        # Create thesis
        new_thesis = Thesis(
            title=title,
            description=description,
            author_id=int(student_id) if student_id and student_id != "" else None,
            frozen=False,
            level=level,
            created_at=int(time.time()),
        )
        db.session.add(new_thesis)
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
        thesis = Thesis.query.get(thesis_id)
        if thesis:
            thesis.title = title
            thesis.description = description
            thesis.level = level
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

    try:
        # Get thesis
        thesis = Thesis.query.get(thesis_id)
        if thesis:
            # Delete related records first
            Thesis_Status.query.filter_by(thesis_id=thesis_id).delete()
            Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).delete()
            Todo.query.filter_by(thesis_id=thesis_id).delete()
            Resource.query.filter_by(thesis_id=thesis_id).delete()
            Thesis_Objective.query.filter_by(thesis_id=thesis_id).delete()
            Thesis_Hypothesis.query.filter_by(thesis_id=thesis_id).delete()
            Thesis_Update.query.filter_by(thesis_id=thesis_id).delete()
            
            # Delete thesis
            db.session.delete(thesis)
            db.session.commit()
            flash("Thesis deleted successfully")
    except Exception as e:
        flash(f"Error deleting thesis: {e}")
    
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
        # Delete associated theses and relationships
        theses = Thesis.query.filter_by(author_id=student_id).all()
        for thesis in theses:
            Thesis_Status.query.filter_by(thesis_id=thesis.id).delete()
            Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).delete()
            Todo.query.filter_by(thesis_id=thesis.id).delete()
            Resource.query.filter_by(thesis_id=thesis.id).delete()
            Thesis_Objective.query.filter_by(thesis_id=thesis.id).delete()
            Thesis_Hypothesis.query.filter_by(thesis_id=thesis.id).delete()
            Thesis_Update.query.filter_by(thesis_id=thesis.id).delete()
            db.session.delete(thesis)
        
        # Delete student
        db.session.delete(student)
        db.session.commit()
        flash("Student and associated data deleted successfully")
    except Exception as e:
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
        thesis = Thesis.query.get(thesis_id)
        if thesis:
            thesis.author_id = int(student_id) if student_id else None
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
        thesis = Thesis.query.get(thesis_id)
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
    supervisor_role = Supervisor_Role.query.filter_by(researcher_id=current_user.id).first()
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
    supervisor_role = Supervisor_Role.query.filter_by(researcher_id=current_user.id).first()
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
    
    return render_template("researcher/supervisor_meeting_note_detail.html", 
                         meeting_note=meeting_note, 
                         thesis=thesis,
                         todos=todos,
                         dt=datetime.fromtimestamp)


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
    supervisor_role = Supervisor_Role.query.filter_by(researcher_id=current_user.id).first()
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

@researcher.route("/researcher/project/<int:project_id>/updates")
@login_required
def project_updates(project_id):
    """
    Display all updates for a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    # Get all updates
    updates = ResearchProject_Update.query.filter_by(project_id=project_id).order_by(ResearchProject_Update.created_at.desc()).all()

    return render_template(
        "researcher/project_updates.html",
        current_user=current_user,
        project=project,
        updates=updates,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


@researcher.route("/researcher/project/<int:project_id>/add_update", methods=["POST"])
@login_required
def add_project_update(project_id):
    """
    Add a new update to a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    content = request.form.get("content")
    update_type = request.form.get("update_type", "progress")

    if not content:
        flash("Update content is required")
        return redirect(url_for("researcher.project_detail", project_id=project_id))

    try:
        new_update = ResearchProject_Update(
            project_id=project_id,
            author_id=current_user.id,
            update_type=update_type,
            content=content,
            created_at=int(time.time())
        )
        db.session.add(new_update)
        db.session.commit()
        flash("Update added successfully")
    except Exception as e:
        flash(f"Error adding update: {e}")

    return redirect(url_for("researcher.project_detail", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/todos")
@login_required
def project_todos(project_id):
    """
    Display all todos for a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    # Get all todos
    todos = ResearchProject_Todo.query.filter_by(project_id=project_id).order_by(ResearchProject_Todo.created_at.desc()).all()

    # Get all collaborators for assignment dropdown
    collaborators = ResearchProject_Collaborator.query.filter_by(project_id=project_id).all()
    collaborator_users = [project.researcher]  # Include project owner
    for collab in collaborators:
        user = User_mgmt.query.get(collab.collaborator_id)
        if user:
            collaborator_users.append(user)

    return render_template(
        "researcher/project_todos.html",
        current_user=current_user,
        project=project,
        todos=todos,
        collaborator_users=collaborator_users,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


@researcher.route("/researcher/project/<int:project_id>/add_todo", methods=["POST"])
@login_required
def add_project_todo(project_id):
    """
    Add a new todo to a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    title = request.form.get("title")
    description = request.form.get("description", "")
    priority = request.form.get("priority", "medium")
    assigned_to_id = request.form.get("assigned_to_id")
    due_date = request.form.get("due_date")

    if not title:
        flash("Todo title is required")
        return redirect(url_for("researcher.project_todos", project_id=project_id))

    try:
        # Convert due_date to timestamp if provided
        due_date_timestamp = None
        if due_date:
            due_date_timestamp = int(datetime.strptime(due_date, "%Y-%m-%d").timestamp())

        new_todo = ResearchProject_Todo(
            project_id=project_id,
            author_id=current_user.id,
            title=title,
            description=description,
            priority=priority,
            assigned_to_id=int(assigned_to_id) if assigned_to_id else None,
            due_date=due_date_timestamp,
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        db.session.add(new_todo)
        db.session.commit()
        flash("Todo added successfully")
    except Exception as e:
        flash(f"Error adding todo: {e}")

    return redirect(url_for("researcher.project_todos", project_id=project_id))


@researcher.route("/researcher/project_todo/<int:todo_id>/complete", methods=["POST"])
@login_required
def complete_project_todo(todo_id):
    """
    Mark a project todo as completed
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    todo = ResearchProject_Todo.query.get(todo_id)
    if not todo:
        abort(404)

    # Check access to the project
    project = todo.project
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    try:
        todo.status = "completed"
        todo.completed_at = int(time.time())
        todo.updated_at = int(time.time())
        db.session.commit()
        flash("Todo marked as completed")
    except Exception as e:
        flash(f"Error completing todo: {e}")

    return redirect(url_for("researcher.project_todos", project_id=project.id))


@researcher.route("/researcher/project/<int:project_id>/resources")
@login_required
def project_resources(project_id):
    """
    Display all resources for a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    # Get all resources
    resources = ResearchProject_Resource.query.filter_by(project_id=project_id).order_by(ResearchProject_Resource.created_at.desc()).all()

    return render_template(
        "researcher/project_resources.html",
        current_user=current_user,
        project=project,
        resources=resources,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


@researcher.route("/researcher/project/<int:project_id>/add_resource", methods=["POST"])
@login_required
def add_project_resource(project_id):
    """
    Add a new resource to a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    resource_url = request.form.get("resource_url")
    resource_type = request.form.get("resource_type", "link")
    description = request.form.get("description", "")

    if not resource_url:
        flash("Resource URL is required")
        return redirect(url_for("researcher.project_resources", project_id=project_id))

    try:
        new_resource = ResearchProject_Resource(
            project_id=project_id,
            resource_type=resource_type,
            resource_url=resource_url,
            description=description,
            created_at=int(time.time())
        )
        db.session.add(new_resource)
        db.session.commit()
        flash("Resource added successfully")
    except Exception as e:
        flash(f"Error adding resource: {e}")

    return redirect(url_for("researcher.project_resources", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/objectives")
@login_required
def project_objectives(project_id):
    """
    Display all objectives for a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    # Get all objectives
    objectives = ResearchProject_Objective.query.filter_by(project_id=project_id).order_by(ResearchProject_Objective.created_at.desc()).all()

    return render_template(
        "researcher/project_objectives.html",
        current_user=current_user,
        project=project,
        objectives=objectives,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


@researcher.route("/researcher/project/<int:project_id>/add_objective", methods=["POST"])
@login_required
def add_project_objective(project_id):
    """
    Add a new objective to a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    title = request.form.get("title")
    description = request.form.get("description")

    if not title or not description:
        flash("Title and description are required")
        return redirect(url_for("researcher.project_objectives", project_id=project_id))

    try:
        new_objective = ResearchProject_Objective(
            project_id=project_id,
            author_id=current_user.id,
            title=title,
            description=description,
            created_at=int(time.time())
        )
        db.session.add(new_objective)
        db.session.commit()
        flash("Objective added successfully")
    except Exception as e:
        flash(f"Error adding objective: {e}")

    return redirect(url_for("researcher.project_objectives", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/hypotheses")
@login_required
def project_hypotheses(project_id):
    """
    Display all hypotheses for a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    # Get all hypotheses
    hypotheses = ResearchProject_Hypothesis.query.filter_by(project_id=project_id).order_by(ResearchProject_Hypothesis.created_at.desc()).all()

    return render_template(
        "researcher/project_hypotheses.html",
        current_user=current_user,
        project=project,
        hypotheses=hypotheses,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


@researcher.route("/researcher/project/<int:project_id>/add_hypothesis", methods=["POST"])
@login_required
def add_project_hypothesis(project_id):
    """
    Add a new hypothesis to a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    title = request.form.get("title")
    description = request.form.get("description")

    if not title or not description:
        flash("Title and description are required")
        return redirect(url_for("researcher.project_hypotheses", project_id=project_id))

    try:
        new_hypothesis = ResearchProject_Hypothesis(
            project_id=project_id,
            author_id=current_user.id,
            title=title,
            description=description,
            created_at=int(time.time())
        )
        db.session.add(new_hypothesis)
        db.session.commit()
        flash("Hypothesis added successfully")
    except Exception as e:
        flash(f"Error adding hypothesis: {e}")

    return redirect(url_for("researcher.project_hypotheses", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/meeting_notes")
@login_required  
def project_meeting_notes(project_id):
    """
    Display all meeting notes for a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    # Get all meeting notes
    meeting_notes = ResearchProject_MeetingNote.query.filter_by(project_id=project_id).order_by(ResearchProject_MeetingNote.created_at.desc()).all()

    return render_template(
        "researcher/project_meeting_notes.html",
        current_user=current_user,
        project=project,
        meeting_notes=meeting_notes,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


@researcher.route("/researcher/project/<int:project_id>/add_meeting_note", methods=["POST"])
@login_required
def add_project_meeting_note(project_id):
    """
    Add a new meeting note to a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    title = request.form.get("title")
    content = request.form.get("content")

    if not title or not content:
        flash("Title and content are required")
        return redirect(url_for("researcher.project_meeting_notes", project_id=project_id))

    try:
        new_meeting_note = ResearchProject_MeetingNote(
            project_id=project_id,
            author_id=current_user.id,
            title=title,
            content=content,
            created_at=int(time.time()),
            updated_at=int(time.time())
        )
        db.session.add(new_meeting_note)
        db.session.commit()
        flash("Meeting note added successfully")
    except Exception as e:
        flash(f"Error adding meeting note: {e}")

    return redirect(url_for("researcher.project_meeting_notes", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/change_status", methods=["POST"])
@login_required
def change_project_status(project_id):
    """
    Change the status of a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = ResearchProject.query.get(project_id)
    if not project:
        abort(404)

    # Only project owner can change status
    if project.researcher_id != current_user.id:
        abort(403)

    new_status = request.form.get("status")
    if not new_status:
        flash("Status is required")
        return redirect(url_for("researcher.project_detail", project_id=project_id))

    try:
        # Add status history entry
        status_entry = ResearchProject_Status(
            project_id=project_id,
            status=new_status,
            updated_at=int(time.time())
        )
        db.session.add(status_entry)
        db.session.commit()
        flash("Project status updated successfully")
    except Exception as e:
        flash(f"Error updating status: {e}")

    return redirect(url_for("researcher.project_detail", project_id=project_id))


# Missing route: delete_project_resource
@researcher.route("/researcher/delete_project_resource/<int:resource_id>", methods=["POST", "DELETE"])
@login_required
def delete_project_resource(resource_id):
    """
    Delete a project resource
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    resource = ResearchProject_Resource.query.get(resource_id)
    if not resource:
        flash("Resource not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(resource.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to delete this resource")
        return redirect(url_for("researcher.projects"))

    try:
        db.session.delete(resource)
        db.session.commit()
        flash("Resource deleted successfully")
    except Exception as e:
        flash(f"Error deleting resource: {e}")

    return redirect(url_for("researcher.project_resources", project_id=project.id))


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
        thesis = Thesis.query.get(thesis_id)
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
        thesis = Thesis.query.get(thesis_id)
        if thesis:
            thesis.frozen = False
            db.session.commit()
            flash("Thesis unfrozen successfully")
    except Exception as e:
        flash(f"Error unfreezing thesis: {e}")
    
    return redirect(url_for("researcher.supervisor_theses"))


# Additional CRUD operations for project resources
@researcher.route("/researcher/edit_project_resource/<int:resource_id>", methods=["POST"])
@login_required
def edit_project_resource(resource_id):
    """
    Edit a project resource
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    resource = ResearchProject_Resource.query.get(resource_id)
    if not resource:
        flash("Resource not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(resource.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to edit this resource")
        return redirect(url_for("researcher.projects"))

    resource_type = request.form.get("resource_type")
    resource_url = request.form.get("resource_url")
    description = request.form.get("description")

    if not resource_type or not resource_url:
        flash("Resource type and URL are required")
        return redirect(url_for("researcher.project_resources", project_id=project.id))

    try:
        resource.resource_type = resource_type
        resource.resource_url = resource_url
        resource.description = description
        db.session.commit()
        flash("Resource updated successfully")
    except Exception as e:
        flash(f"Error updating resource: {e}")

    return redirect(url_for("researcher.project_resources", project_id=project.id))


# CRUD operations for project todos
@researcher.route("/researcher/edit_project_todo/<int:todo_id>", methods=["POST"])
@login_required
def edit_project_todo(todo_id):
    """
    Edit a project todo
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    todo = ResearchProject_Todo.query.get(todo_id)
    if not todo:
        flash("Todo not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(todo.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to edit this todo")
        return redirect(url_for("researcher.projects"))

    title = request.form.get("title")
    description = request.form.get("description")
    priority = request.form.get("priority", "medium")

    if not title:
        flash("Title is required")
        return redirect(url_for("researcher.project_todos", project_id=project.id))

    try:
        todo.title = title
        todo.description = description
        todo.priority = priority
        todo.updated_at = int(time.time())
        db.session.commit()
        flash("Todo updated successfully")
    except Exception as e:
        flash(f"Error updating todo: {e}")

    return redirect(url_for("researcher.project_todos", project_id=project.id))


@researcher.route("/researcher/delete_project_todo/<int:todo_id>", methods=["POST", "DELETE"])
@login_required
def delete_project_todo(todo_id):
    """
    Delete a project todo
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    todo = ResearchProject_Todo.query.get(todo_id)
    if not todo:
        flash("Todo not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(todo.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to delete this todo")
        return redirect(url_for("researcher.projects"))

    try:
        db.session.delete(todo)
        db.session.commit()
        flash("Todo deleted successfully")
    except Exception as e:
        flash(f"Error deleting todo: {e}")

    return redirect(url_for("researcher.project_todos", project_id=project.id))


# CRUD operations for project objectives
@researcher.route("/researcher/edit_project_objective/<int:objective_id>", methods=["POST"])
@login_required
def edit_project_objective(objective_id):
    """
    Edit a project objective
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    objective = ResearchProject_Objective.query.get(objective_id)
    if not objective:
        flash("Objective not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(objective.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to edit this objective")
        return redirect(url_for("researcher.projects"))

    title = request.form.get("title")
    description = request.form.get("description")

    if not title:
        flash("Title is required")
        return redirect(url_for("researcher.project_objectives", project_id=project.id))

    try:
        objective.title = title
        objective.description = description
        db.session.commit()
        flash("Objective updated successfully")
    except Exception as e:
        flash(f"Error updating objective: {e}")

    return redirect(url_for("researcher.project_objectives", project_id=project.id))


@researcher.route("/researcher/delete_project_objective/<int:objective_id>", methods=["POST", "DELETE"])
@login_required
def delete_project_objective(objective_id):
    """
    Delete a project objective
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    objective = ResearchProject_Objective.query.get(objective_id)
    if not objective:
        flash("Objective not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(objective.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to delete this objective")
        return redirect(url_for("researcher.projects"))

    try:
        db.session.delete(objective)
        db.session.commit()
        flash("Objective deleted successfully")
    except Exception as e:
        flash(f"Error deleting objective: {e}")

    return redirect(url_for("researcher.project_objectives", project_id=project.id))


# CRUD operations for project hypotheses
@researcher.route("/researcher/edit_project_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def edit_project_hypothesis(hypothesis_id):
    """
    Edit a project hypothesis
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    hypothesis = ResearchProject_Hypothesis.query.get(hypothesis_id)
    if not hypothesis:
        flash("Hypothesis not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(hypothesis.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to edit this hypothesis")
        return redirect(url_for("researcher.projects"))

    title = request.form.get("title")
    description = request.form.get("description")

    if not title:
        flash("Title is required")
        return redirect(url_for("researcher.project_hypotheses", project_id=project.id))

    try:
        hypothesis.title = title
        hypothesis.description = description
        db.session.commit()
        flash("Hypothesis updated successfully")
    except Exception as e:
        flash(f"Error updating hypothesis: {e}")

    return redirect(url_for("researcher.project_hypotheses", project_id=project.id))


@researcher.route("/researcher/delete_project_hypothesis/<int:hypothesis_id>", methods=["POST", "DELETE"])
@login_required
def delete_project_hypothesis(hypothesis_id):
    """
    Delete a project hypothesis
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    hypothesis = ResearchProject_Hypothesis.query.get(hypothesis_id)
    if not hypothesis:
        flash("Hypothesis not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(hypothesis.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to delete this hypothesis")
        return redirect(url_for("researcher.projects"))

    try:
        db.session.delete(hypothesis)
        db.session.commit()
        flash("Hypothesis deleted successfully")
    except Exception as e:
        flash(f"Error deleting hypothesis: {e}")

    return redirect(url_for("researcher.project_hypotheses", project_id=project.id))


# CRUD operations for project meeting notes
@researcher.route("/researcher/edit_project_meeting_note/<int:note_id>", methods=["POST"])
@login_required
def edit_project_meeting_note(note_id):
    """
    Edit a project meeting note
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    note = ResearchProject_MeetingNote.query.get(note_id)
    if not note:
        flash("Meeting note not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(note.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to edit this meeting note")
        return redirect(url_for("researcher.projects"))

    title = request.form.get("title")
    content = request.form.get("content")

    if not title or not content:
        flash("Title and content are required")
        return redirect(url_for("researcher.project_meeting_notes", project_id=project.id))

    try:
        note.title = title
        note.content = content
        note.updated_at = int(time.time())
        db.session.commit()
        flash("Meeting note updated successfully")
    except Exception as e:
        flash(f"Error updating meeting note: {e}")

    return redirect(url_for("researcher.project_meeting_notes", project_id=project.id))


@researcher.route("/researcher/delete_project_meeting_note/<int:note_id>", methods=["POST", "DELETE"])
@login_required
def delete_project_meeting_note(note_id):
    """
    Delete a project meeting note
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    note = ResearchProject_MeetingNote.query.get(note_id)
    if not note:
        flash("Meeting note not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(note.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to delete this meeting note")
        return redirect(url_for("researcher.projects"))

    try:
        db.session.delete(note)
        db.session.commit()
        flash("Meeting note deleted successfully")
    except Exception as e:
        flash(f"Error deleting meeting note: {e}")

    return redirect(url_for("researcher.project_meeting_notes", project_id=project.id))


# CRUD operations for project updates
@researcher.route("/researcher/edit_project_update/<int:update_id>", methods=["POST"])
@login_required
def edit_project_update(update_id):
    """
    Edit a project update
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    update = ResearchProject_Update.query.get(update_id)
    if not update:
        flash("Update not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(update.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to edit this update")
        return redirect(url_for("researcher.projects"))

    update_type = request.form.get("update_type")
    content = request.form.get("content")

    if not update_type or not content:
        flash("Update type and content are required")
        return redirect(url_for("researcher.project_updates", project_id=project.id))

    try:
        update.update_type = update_type
        update.content = content
        db.session.commit()
        flash("Update edited successfully")
    except Exception as e:
        flash(f"Error editing update: {e}")

    return redirect(url_for("researcher.project_updates", project_id=project.id))


@researcher.route("/researcher/delete_project_update/<int:update_id>", methods=["POST", "DELETE"])
@login_required
def delete_project_update(update_id):
    """
    Delete a project update
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    update = ResearchProject_Update.query.get(update_id)
    if not update:
        flash("Update not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = ResearchProject.query.get(update.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to delete this update")
        return redirect(url_for("researcher.projects"))

    try:
        db.session.delete(update)
        db.session.commit()
        flash("Update deleted successfully")
    except Exception as e:
        flash(f"Error deleting update: {e}")

    return redirect(url_for("researcher.project_updates", project_id=project.id))


# ==============================================================================
# DETAIL ROUTES WITH CRUD FUNCTIONALITY FOR MEETING NOTES, TODOS, AND UPDATES
# ==============================================================================

@researcher.route("/researcher/project_meeting_note/<int:note_id>")
@login_required
def project_meeting_note_detail(note_id):
    """
    Display detailed view of a research project meeting note with full CRUD capabilities
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    # Get the meeting note
    meeting_note = ResearchProject_MeetingNote.query.get(note_id)
    if not meeting_note:
        flash("Meeting note not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = meeting_note.project
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to view this meeting note")
        return redirect(url_for("researcher.projects"))

    # Get project todos for reference dropdown
    todos = ResearchProject_Todo.query.filter_by(project_id=project.id).order_by(ResearchProject_Todo.created_at.desc()).all()

    return render_template(
        "researcher/project_meeting_note_detail.html",
        current_user=current_user,
        meeting_note=meeting_note,
        project=project,
        todos=todos,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


@researcher.route("/researcher/project_todo/<int:todo_id>")
@login_required
def project_todo_detail(todo_id):
    """
    Display detailed view of a research project todo with full CRUD capabilities
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    # Get the todo
    todo = ResearchProject_Todo.query.get(todo_id)
    if not todo:
        flash("Todo not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = todo.project
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to view this todo")
        return redirect(url_for("researcher.projects"))

    # Get all collaborators for assignment dropdown
    collaborators = ResearchProject_Collaborator.query.filter_by(project_id=project.id).all()
    collaborator_users = [project.researcher]  # Include project owner
    for collab in collaborators:
        user = User_mgmt.query.get(collab.collaborator_id)
        if user:
            collaborator_users.append(user)

    # Get referenced updates (if any todo reference system exists)
    referenced_updates = []
    try:
        referenced_updates = db.session.query(ResearchProject_Update)\
            .join(ResearchProject_TodoReference)\
            .filter(ResearchProject_TodoReference.todo_id == todo_id)\
            .order_by(ResearchProject_Update.created_at.desc()).all()
    except:
        pass  # In case TodoReference relationship doesn't exist yet

    return render_template(
        "researcher/project_todo_detail.html",
        current_user=current_user,
        todo=todo,
        project=project,
        collaborator_users=collaborator_users,
        referenced_updates=referenced_updates,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )


@researcher.route("/researcher/project_update/<int:update_id>")
@login_required
def project_update_detail(update_id):
    """
    Display detailed view of a research project update with full CRUD capabilities
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    # Get the update
    update = ResearchProject_Update.query.get(update_id)
    if not update:
        flash("Update not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = update.project
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to view this update")
        return redirect(url_for("researcher.projects"))

    # Get project todos for reference
    todos = ResearchProject_Todo.query.filter_by(project_id=project.id).order_by(ResearchProject_Todo.created_at.desc()).all()

    # Get referenced todos (if any todo reference system exists)
    referenced_todos = []
    try:
        referenced_todos = db.session.query(ResearchProject_Todo)\
            .join(ResearchProject_TodoReference)\
            .filter(ResearchProject_TodoReference.update_id == update_id)\
            .order_by(ResearchProject_Todo.created_at.desc()).all()
    except:
        pass  # In case TodoReference relationship doesn't exist yet

    return render_template(
        "researcher/project_update_detail.html",
        current_user=current_user,
        update=update,
        project=project,
        todos=todos,
        referenced_todos=referenced_todos,
        is_owner=(project.researcher_id == current_user.id),
        datetime=datetime,
        dt=datetime.fromtimestamp
    )