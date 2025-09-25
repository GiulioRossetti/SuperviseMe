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
        is_owner=(project.researcher_id == current_user.id)
    )