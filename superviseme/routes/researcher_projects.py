"""Research project routes (projects, collaborators, updates, todos, resources, objectives,
hypotheses, meeting notes). Registered on the ``researcher`` blueprint; imported at the bottom of
``researcher.py`` so every endpoint name and URL stays the same."""
from flask import Blueprint, request, render_template, abort, redirect, url_for, jsonify, flash, current_app
import logging

logger = logging.getLogger(__name__)
from flask_login import login_required, current_user
from sqlalchemy import select, and_, func, or_
from superviseme.utils import security
from superviseme.utils.miscellanea import check_privileges, user_has_supervisor_role
from superviseme.utils.thesis_resources import normalize_resource_url, resolve_resource_type
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
from werkzeug.security import generate_password_hash
import time
from flask_babel import gettext as _

from superviseme.routes.researcher import researcher, COLLABORATOR_ROLES, READ_ONLY_ROLES, _owned_project_or_404, _project_form_context  # noqa: E402


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
        collaborators = ResearchProject_Collaborator.query.filter_by(project_id=project.id, status="accepted").all()
        collaborator_users = []
        for collab in collaborators:
            user = db.session.get(User_mgmt, collab.collaborator_id)
            if user:
                collaborator_users.append({"user": user, "role": collab.role, "status": collab.status})
        
        projects_with_collaborators.append({
            "project": project,
            "collaborators": collaborator_users
        })

    return render_template(
        "researcher/projects.html",
        current_user=current_user,
        projects_with_collaborators=projects_with_collaborators,
        has_supervisor_role=user_has_supervisor_role(current_user),
        **_project_form_context(),
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

    from superviseme.utils import projects as pj

    title = (request.form.get("title") or "").strip()[:100]
    description = request.form.get("description")
    level = pj.clean_level(request.form.get("level"))

    if not title or not description:
        flash("Title and description are required")
        return redirect(request.referrer or url_for("researcher.projects"))

    try:
        new_project = ResearchProject(
            title=title,
            description=description,
            researcher_id=current_user.id,
            frozen=False,
            level=level,
            area=pj.clean_area(request.form.get("area")),
            tags=pj.normalize_tags(request.form.get("tags")),
            created_at=int(time.time()),
        )
        error = pj.set_parent(new_project, request.form.get("parent_id"), current_user)
        if error:
            flash(error)
            return redirect(request.referrer or url_for("researcher.projects"))
        db.session.add(new_project)
        db.session.commit()
        added, errors = pj.add_images(new_project, request.files.getlist("images"))
        for err in errors:
            flash(err)

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

    project = db.session.get(ResearchProject, project_id)
    if not project or project.researcher_id != current_user.id:
        flash("Project not found or access denied")
        return redirect(url_for("researcher.projects"))

    from superviseme.utils import projects as pj

    try:
        if title:
            project.title = title.strip()[:100]
        if description:
            project.description = description
        if level:
            project.level = pj.clean_level(level)
        if "area" in request.form:
            project.area = pj.clean_area(request.form.get("area"))
        if "tags" in request.form:
            project.tags = pj.normalize_tags(request.form.get("tags"))
        if "parent_id" in request.form:
            error = pj.set_parent(project, request.form.get("parent_id"), current_user)
            if error:
                flash(error)
                return redirect(request.referrer or url_for("researcher.projects"))
        db.session.commit()
        added, errors = pj.add_images(project, request.files.getlist("images"))
        for err in errors:
            flash(err)
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

    project = db.session.get(ResearchProject, project_id)
    if not project or project.researcher_id != current_user.id:
        return jsonify({"status": "error", "message": "Project not found or access denied"}), 404

    try:
        from superviseme.utils import projects as pj
        pj.delete_project_cascade(project)

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
    role = (request.form.get("role") or "collaborator").strip().lower()
    if role not in COLLABORATOR_ROLES:
        role = "collaborator"

    if not project_id or not collaborator_email:
        flash("Project ID and collaborator email are required")
        return redirect(request.referrer)

    project = db.session.get(ResearchProject, project_id)
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
        flash("User is already a collaborator on this project (or has a pending invitation)")
        return redirect(request.referrer)

    try:
        new_collaborator = ResearchProject_Collaborator(
            project_id=project_id,
            collaborator_id=collaborator.id,
            role=role,
            status="pending",
            added_at=int(time.time())
        )
        db.session.add(new_collaborator)
        db.session.commit()

        try:
            from superviseme.utils.notifications import create_notification
            create_notification(
                recipient_id=collaborator.id,
                actor_id=current_user.id,
                notification_type="project_invitation",
                title=f"Invitation to project: {project.title}",
                message=f"{current_user.name} {current_user.surname} invited you to collaborate on "
                        f"\"{project.title}\" as {role}. Accept or decline from your dashboard.",
                action_url=url_for("researcher.dashboard"),
            )
        except Exception:  # notification failures must not block the invitation
            current_app.logger.exception("Could not notify project invitee")

        flash(f"Invitation sent to {collaborator.name} {collaborator.surname}")
        return redirect(url_for("researcher.projects"))
    except Exception as e:
        flash(f"Error adding collaborator: {e}")
        return redirect(request.referrer)


def _pending_invitation_or_404(invitation_id):
    inv = db.session.get(ResearchProject_Collaborator, invitation_id)
    if inv is None or inv.collaborator_id != current_user.id or inv.status != "pending":
        abort(404)
    return inv


def _notify_inviter(inv, accepted):
    try:
        from superviseme.utils.notifications import create_notification
        project = inv.project
        verb = "accepted" if accepted else "declined"
        create_notification(
            recipient_id=project.researcher_id,
            actor_id=current_user.id,
            notification_type="project_invitation_reply",
            title=f"Invitation {verb}: {project.title}",
            message=f"{current_user.name} {current_user.surname} {verb} your invitation to \"{project.title}\".",
            action_url=url_for("researcher.project_detail", project_id=project.id),
        )
    except Exception:
        current_app.logger.exception("Could not notify project owner")


def _resolve_invitation_notifications(inv):
    """Mark the invitee's pending-invitation notifications for this project as read once they answered."""
    from superviseme.models import Notification
    project = db.session.get(ResearchProject, inv.project_id)
    if not project:
        return
    Notification.query.filter_by(recipient_id=current_user.id, notification_type="project_invitation", is_read=False,
                                 title=f"Invitation to project: {project.title}").update({"is_read": True}, synchronize_session=False)
    db.session.commit()


@researcher.route("/researcher/invitations/<int:invitation_id>/accept", methods=["POST"])
@login_required
def accept_project_invitation(invitation_id):
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    inv = _pending_invitation_or_404(invitation_id)
    inv.status = "accepted"
    db.session.commit()
    _resolve_invitation_notifications(inv)
    _notify_inviter(inv, True)
    flash("Invitation accepted")
    return redirect(url_for("researcher.project_detail", project_id=inv.project_id))


@researcher.route("/researcher/invitations/<int:invitation_id>/decline", methods=["POST"])
@login_required
def decline_project_invitation(invitation_id):
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    inv = _pending_invitation_or_404(invitation_id)
    _notify_inviter(inv, False)
    _resolve_invitation_notifications(inv)
    db.session.delete(inv)
    db.session.commit()
    flash("Invitation declined")
    return redirect(url_for("researcher.dashboard"))


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

    project = db.session.get(ResearchProject, project_id)
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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check if user has access (either owner or collaborator)
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None

    if not has_access:
        abort(403)

    # Get collaborators
    collaborators = ResearchProject_Collaborator.query.filter_by(project_id=project_id).all()
    collaborator_users = []
    for collab in collaborators:
        user = db.session.get(User_mgmt, collab.collaborator_id)
        if user:
            collaborator_users.append({"user": user, "role": collab.role, "status": collab.status})

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
        dt=datetime.fromtimestamp,
        linked=__import__("superviseme.utils.projects", fromlist=["x"]).linked_projects(project),
        ancestors=list(reversed(__import__("superviseme.utils.projects", fromlist=["x"]).ancestors(project))),
        **_project_form_context(exclude=project),
    )


@researcher.route("/researcher/project/<int:project_id>/updates")
@login_required
def project_updates(project_id):
    """
    Display all updates for a research project
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
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
        user = db.session.get(User_mgmt, collab.collaborator_id)
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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    todo = db.session.get(ResearchProject_Todo, todo_id)
    if not todo:
        abort(404)

    # Check access to the project
    project = todo.project
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
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

    project = db.session.get(ResearchProject, project_id)
    if not project:
        abort(404)

    # Check access
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project_id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    project = db.session.get(ResearchProject, project_id)
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


@researcher.route("/researcher/delete_project_resource/<int:resource_id>", methods=["POST", "DELETE"])
@login_required
def delete_project_resource(resource_id):
    """
    Delete a project resource
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    resource = db.session.get(ResearchProject_Resource, resource_id)
    if not resource:
        flash("Resource not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, resource.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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


@researcher.route("/researcher/edit_project_resource/<int:resource_id>", methods=["POST"])
@login_required
def edit_project_resource(resource_id):
    """
    Edit a project resource
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    resource = db.session.get(ResearchProject_Resource, resource_id)
    if not resource:
        flash("Resource not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, resource.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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


@researcher.route("/researcher/edit_project_todo/<int:todo_id>", methods=["POST"])
@login_required
def edit_project_todo(todo_id):
    """
    Edit a project todo
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    todo = db.session.get(ResearchProject_Todo, todo_id)
    if not todo:
        flash("Todo not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, todo.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    todo = db.session.get(ResearchProject_Todo, todo_id)
    if not todo:
        flash("Todo not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, todo.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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


@researcher.route("/researcher/edit_project_objective/<int:objective_id>", methods=["POST"])
@login_required
def edit_project_objective(objective_id):
    """
    Edit a project objective
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    objective = db.session.get(ResearchProject_Objective, objective_id)
    if not objective:
        flash("Objective not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, objective.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    objective = db.session.get(ResearchProject_Objective, objective_id)
    if not objective:
        flash("Objective not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, objective.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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


@researcher.route("/researcher/edit_project_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def edit_project_hypothesis(hypothesis_id):
    """
    Edit a project hypothesis
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    hypothesis = db.session.get(ResearchProject_Hypothesis, hypothesis_id)
    if not hypothesis:
        flash("Hypothesis not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, hypothesis.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    hypothesis = db.session.get(ResearchProject_Hypothesis, hypothesis_id)
    if not hypothesis:
        flash("Hypothesis not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, hypothesis.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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


@researcher.route("/researcher/edit_project_meeting_note/<int:note_id>", methods=["POST"])
@login_required
def edit_project_meeting_note(note_id):
    """
    Edit a project meeting note
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    note = db.session.get(ResearchProject_MeetingNote, note_id)
    if not note:
        flash("Meeting note not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, note.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    note = db.session.get(ResearchProject_MeetingNote, note_id)
    if not note:
        flash("Meeting note not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, note.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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


@researcher.route("/researcher/edit_project_update/<int:update_id>", methods=["POST"])
@login_required
def edit_project_update(update_id):
    """
    Edit a project update
    """
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check

    update = db.session.get(ResearchProject_Update, update_id)
    if not update:
        flash("Update not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, update.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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

    update = db.session.get(ResearchProject_Update, update_id)
    if not update:
        flash("Update not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = db.session.get(ResearchProject, update.project_id)
    if not project:
        flash("Project not found")
        return redirect(url_for("researcher.projects"))

    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None and collaboration.role not in READ_ONLY_ROLES

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
    meeting_note = db.session.get(ResearchProject_MeetingNote, note_id)
    if not meeting_note:
        flash("Meeting note not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = meeting_note.project
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
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
    todo = db.session.get(ResearchProject_Todo, todo_id)
    if not todo:
        flash("Todo not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = todo.project
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
        ).first()
        has_access = collaboration is not None

    if not has_access:
        flash("You don't have permission to view this todo")
        return redirect(url_for("researcher.projects"))

    # Get all collaborators for assignment dropdown
    collaborators = ResearchProject_Collaborator.query.filter_by(project_id=project.id).all()
    collaborator_users = [project.researcher]  # Include project owner
    for collab in collaborators:
        user = db.session.get(User_mgmt, collab.collaborator_id)
        if user:
            collaborator_users.append(user)

    # Get referenced updates (if any todo reference system exists)
    referenced_updates = []
    try:
        referenced_updates = db.session.query(ResearchProject_Update)\
            .join(ResearchProject_TodoReference)\
            .filter(ResearchProject_TodoReference.todo_id == todo_id)\
            .order_by(ResearchProject_Update.created_at.desc()).all()
    except Exception as exc:
        logger.warning("TodoReference query failed for todo_id=%s: %s", todo_id, exc)

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
    update = db.session.get(ResearchProject_Update, update_id)
    if not update:
        flash("Update not found")
        return redirect(url_for("researcher.projects"))

    # Check if user has access to the project
    project = update.project
    has_access = project.researcher_id == current_user.id
    if not has_access:
        collaboration = ResearchProject_Collaborator.query.filter_by(
            project_id=project.id, collaborator_id=current_user.id, status="accepted"
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
    except Exception as exc:
        logger.warning("TodoReference query failed for update_id=%s: %s", update_id, exc)

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


@researcher.route("/researcher/project/<int:project_id>/images", methods=["POST"])
@login_required
def add_project_images(project_id):
    from superviseme.utils import projects as pj
    project, denied = _owned_project_or_404(project_id)
    if denied is not None:
        return denied
    added, errors = pj.add_images(project, request.files.getlist("images"))
    if added:
        flash(_("%(n)d image(s) added.", n=added))
    for err in errors:
        flash(err)
    if not added and not errors:
        flash(_("No file selected."))
    return redirect(url_for("researcher.project_detail", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/images/<int:image_id>/delete", methods=["POST"])
@login_required
def delete_project_image(project_id, image_id):
    from superviseme.utils import projects as pj
    project, denied = _owned_project_or_404(project_id)
    if denied is not None:
        return denied
    pj.delete_image(project, image_id)
    return redirect(url_for("researcher.project_detail", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/links", methods=["POST"])
@login_required
def add_project_link(project_id):
    from superviseme.utils import projects as pj
    project, denied = _owned_project_or_404(project_id)
    if denied is not None:
        return denied
    error = pj.add_link(project, request.form.get("linked_id"), request.form.get("relation"), current_user)
    flash(error or _("Projects linked."))
    return redirect(url_for("researcher.project_detail", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/links/<int:link_id>/delete", methods=["POST"])
@login_required
def delete_project_link(project_id, link_id):
    from superviseme.utils import projects as pj
    project, denied = _owned_project_or_404(project_id)
    if denied is not None:
        return denied
    pj.remove_link(project, link_id)
    return redirect(url_for("researcher.project_detail", project_id=project_id))


@researcher.route("/researcher/project/<int:project_id>/report")
@login_required
def project_report(project_id):
    from flask import Response
    from superviseme.utils import projects as pj
    privilege_check = check_privileges(current_user.username, role="researcher")
    if privilege_check is not True:
        return privilege_check
    project = ResearchProject.query.get_or_404(project_id)
    if not pj.user_can_access(current_user, project):
        abort(403)
    data = pj.project_report(project)
    stem = "project-%d-report" % project.id
    if request.args.get("format") == "md":
        body, mimetype, ext = pj.report_markdown(data), "text/markdown; charset=utf-8", "md"
    else:
        body, mimetype, ext = pj.report_pdf(data), "application/pdf", "pdf"
    resp = Response(body, mimetype=mimetype)
    resp.headers["Content-Disposition"] = 'attachment; filename="%s.%s"' % (stem, ext)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp
