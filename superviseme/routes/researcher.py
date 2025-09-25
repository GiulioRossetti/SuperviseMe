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
    This route displays detailed information about a research project.
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

    return render_template(
        "researcher/project_detail.html",
        current_user=current_user,
        project=project,
        collaborators=collaborator_users,
        has_supervisor_role=user_has_supervisor_role(current_user),
        is_owner=(project.researcher_id == current_user.id),
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

    # Get students supervised by this researcher
    supervised_students = db.session.execute(
        select(User_mgmt, Thesis)
        .join(Thesis, Thesis.author_id == User_mgmt.id)
        .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)
        .where(Thesis_Supervisor.supervisor_id == current_user.id)
        .where(User_mgmt.user_type == "student")
    ).all()

    return render_template(
        "researcher/supervisor_students.html",
        current_user=current_user,
        supervised_students=supervised_students,
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

    return render_template(
        "researcher/supervisor_theses.html",
        current_user=current_user,
        theses=theses,
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
    objectives = Thesis_Objective.query.filter_by(thesis_id=thesis_id).all()
    hypotheses = Thesis_Hypothesis.query.filter_by(thesis_id=thesis_id).all()

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
        has_supervisor_role=True,
        datetime=datetime,
        dt=datetime.fromtimestamp,
        str=str
    )


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