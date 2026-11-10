"""Supervisor: per-thesis workspace (updates, comments, objectives, hypotheses, to-dos, resources, meeting notes).
"""
from flask import request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from superviseme.utils.miscellanea import check_privileges
from superviseme.routes._supervision import ep, supervision_gate
from superviseme.utils.thesis_resources import normalize_resource_url, resolve_resource_type
from superviseme.models import *
from superviseme import db
from datetime import datetime
import time
from flask_babel import gettext as _

from superviseme.routes.supervisor import supervisor


@supervisor.route("/supervisor/post_update", methods=["POST"])
@login_required
def post_update():
    """
    This route handles posting updates to a thesis. It retrieves the necessary data from the form,
    creates a new Update object, and saves it to the database.
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check

    thesis_id = request.form.get("thesis_id")
    content = request.form.get("content")

    # Only a supervisor of this thesis may post supervisor updates on it
    if not Thesis_Supervisor.query.filter_by(thesis_id=thesis_id, supervisor_id=current_user.id).first():
        flash(_("You don't have permission to update this thesis"))
        return redirect(url_for(ep('theses')))

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

    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/post_comment", methods=["POST"])
@login_required
def post_comment():
    """
    This route handles posting comments on updates. It retrieves the necessary data from the form,
    creates a new Update object with the comment, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    update_id = request.form.get("update_id")
    content = request.form.get("content")

    parent_update = Thesis_Update.query.join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis_Update.thesis_id
    ).filter(
        Thesis_Update.id == update_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()

    if not parent_update:
        return redirect(url_for('supervisor.theses_data'))

    new_comment = Thesis_Update(
        thesis_id=parent_update.thesis_id,
        parent_id=parent_update.id,
        author_id=current_user.id,
        content=content,
        update_type="supervisor_comment",
        created_at=int(time.time())
    )

    db.session.add(new_comment)
    db.session.commit()

    return redirect(url_for('supervisor.thesis_detail', thesis_id=parent_update.thesis_id))


@supervisor.route("/supervisor/delete_update/<int:update_id>", methods=["POST"])
@login_required
def delete_update(update_id):
    """
    This route handles deleting an update by its ID. It retrieves the update, deletes it from the database,
    and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify the update belongs to a thesis supervised by the current user
    update = Thesis_Update.query.join(Thesis).join(Thesis_Supervisor).filter(
        Thesis_Update.id == update_id,
        Thesis_Update.update_type == "supervisor_update",
        Thesis_Update.author_id == current_user.id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if update:
        thesis_id = update.thesis_id
        db.session.delete(update)
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/delete_comment", methods=["POST"])
@login_required
def delete_comment():
    """
    This route handles deleting a comment. It retrieves the comment ID from the form,
    deletes the comment from the database, and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    comment_id = request.form.get("comment_id")
    
    # Verify the comment belongs to a thesis supervised by the current user
    comment = Thesis_Update.query.join(Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis_Update.thesis_id).filter(
        Thesis_Update.id == comment_id,
        Thesis_Update.update_type == "supervisor_comment",
        Thesis_Update.parent_id.isnot(None),
        Thesis_Update.author_id == current_user.id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if comment:
        thesis_id = comment.thesis_id
        db.session.delete(comment)
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/modify_update", methods=["POST"])
@login_required
def modify_update():
    """
    This route handles modifying an update. It retrieves the necessary data from the form,
    updates the content of the update in the database, and redirects to the thesis detail page.
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    update_id = request.form.get("update_id")
    new_content = request.form.get("new_content")

    # Verify the update belongs to a thesis supervised by the current user
    update = Thesis_Update.query.join(Thesis).join(Thesis_Supervisor).filter(
        Thesis_Update.id == update_id,
        Thesis_Update.update_type == "supervisor_update",
        Thesis_Update.author_id == current_user.id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if update:
        update.content = new_content
        db.session.commit()
        return redirect(url_for(ep('thesis_detail'), thesis_id=update.thesis_id))

    return redirect(url_for(ep('theses')))


@supervisor.route("/supervisor/modify_comment", methods=["POST"])
@login_required
def modify_comment():
    """
    This route handles modifying a comment. It retrieves the necessary data from the form,
    updates the content of the comment in the database, and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    comment_id = request.form.get("comment_id")
    new_content = request.form.get("new_content")

    comment = Thesis_Update.query.join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis_Update.thesis_id
    ).filter(
        Thesis_Update.id == comment_id,
        Thesis_Update.update_type == "supervisor_comment",
        Thesis_Update.parent_id.isnot(None),
        Thesis_Update.author_id == current_user.id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()

    if comment:
        comment.content = new_content
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=comment.thesis_id))

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/tag_update", methods=["POST"])
@login_required
def tag_update():
    """
    This route handles tagging an update. It retrieves the necessary data from the form,
    updates the update with the new tags, and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    update_id = request.form.get("update_id")
    tags = request.form.get("tags", "")

    update = Thesis_Update.query.join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis_Update.thesis_id
    ).filter(
        Thesis_Update.id == update_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()

    if not update:
        return redirect(url_for('supervisor.theses_data'))

    tag_items = [t.strip() for t in tags.split(",") if t and t.strip()]
    for tag in tag_items:
        existing = Update_Tag.query.filter_by(update_id=update_id, tag=tag).first()
        if not existing:
            db.session.add(Update_Tag(update_id=update_id, tag=tag))

    db.session.commit()
    return redirect(url_for('supervisor.thesis_detail', thesis_id=update.thesis_id))


@supervisor.route("/supervisor/delete_update_tag", methods=["POST"])
@login_required
def delete_update_tag():
    """
    This route handles deleting a tag from an update. It retrieves the tag ID from the form,
    deletes the tag from the database, and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

    tag_id = request.form.get("tag_id")
    tag = Update_Tag.query.get_or_404(tag_id)
    update = db.session.get(Thesis_Update, tag.update_id)
    if not update:
        return redirect(url_for('supervisor.theses_data'))

    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=update.thesis_id, supervisor_id=current_user.id
    ).first()
    if thesis_supervisor:
        db.session.delete(tag)
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=update.thesis_id))

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/freeze_objective/<int:objective_id>", methods=["POST"])
@login_required
def freeze_objective(objective_id):
    """
    This route handles freezing an objective. It retrieves the objective by ID,
    sets the frozen status to True, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify the objective belongs to a thesis supervised by the current user
    objective = Thesis_Objective.query.join(Thesis, Thesis.id == Thesis_Objective.thesis_id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        Thesis_Objective.id == objective_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if objective:
        objective.frozen = True
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=objective.thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/unfreeze_objective/<int:objective_id>", methods=["POST"])
@login_required
def unfreeze_objective(objective_id):
    """
    This route handles unfreezing an objective. It retrieves the objective by ID,
    sets the frozen status to False, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify the objective belongs to a thesis supervised by the current user
    objective = Thesis_Objective.query.join(Thesis, Thesis.id == Thesis_Objective.thesis_id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        Thesis_Objective.id == objective_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if objective:
        objective.frozen = False
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=objective.thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/freeze_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def freeze_hypothesis(hypothesis_id):
    """
    This route handles freezing a hypothesis. It retrieves the hypothesis by ID,
    sets the frozen status to True, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify the hypothesis belongs to a thesis supervised by the current user
    hypothesis = Thesis_Hypothesis.query.join(Thesis, Thesis.id == Thesis_Hypothesis.thesis_id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        Thesis_Hypothesis.id == hypothesis_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if hypothesis:
        hypothesis.frozen = True
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=hypothesis.thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/unfreeze_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def unfreeze_hypothesis(hypothesis_id):
    """
    This route handles unfreezing a hypothesis. It retrieves the hypothesis by ID,
    sets the frozen status to False, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify the hypothesis belongs to a thesis supervised by the current user
    hypothesis = Thesis_Hypothesis.query.join(Thesis, Thesis.id == Thesis_Hypothesis.thesis_id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        Thesis_Hypothesis.id == hypothesis_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if hypothesis:
        hypothesis.frozen = False
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=hypothesis.thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/supervisor/comment_on_update", methods=["POST"])
@login_required
def comment_on_update():
    """
    This route handles adding comments to student updates. It creates a comment
    as a child update linked to the parent update.
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    update_id = request.form.get("update_id")
    comment_content = request.form.get("comment")
    
    # Verify the update belongs to a thesis supervised by the current user
    parent_update = Thesis_Update.query.join(Thesis, Thesis.id == Thesis_Update.thesis_id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        Thesis_Update.id == update_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if parent_update:
        new_comment = Thesis_Update(
            thesis_id=parent_update.thesis_id,
            author_id=current_user.id,
            parent_id=parent_update.id,
            content=comment_content,
            update_type="supervisor_comment",
            created_at=int(time.time())
        )
        
        db.session.add(new_comment)
        db.session.commit()
        
        return redirect(url_for(ep('thesis_detail'), thesis_id=parent_update.thesis_id))
    
    return redirect(url_for(ep('theses')))


@supervisor.route("/supervisor/tag_student_update", methods=["POST"])
@login_required
def tag_student_update():
    """
    This route handles tagging student updates. It adds tags to updates.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    update_id = request.form.get("update_id")
    tag_text = request.form.get("tag")
    
    # Verify the update belongs to a thesis supervised by the current user
    update = Thesis_Update.query.join(Thesis, Thesis.id == Thesis_Update.thesis_id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        Thesis_Update.id == update_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if update and tag_text:
        # Check if tag already exists
        existing_tag = Update_Tag.query.filter_by(update_id=update_id, tag=tag_text).first()
        if not existing_tag:
            new_tag = Update_Tag(
                update_id=update_id,
                tag=tag_text
            )
            db.session.add(new_tag)
            db.session.commit()
        
        return redirect(url_for('supervisor.thesis_detail', thesis_id=update.thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


# Todo routes for supervisors
@supervisor.route("/supervisor/add_todo", methods=["POST"])
@login_required
def add_todo():
    """
    Add a new todo item for a supervised thesis
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    description = request.form.get("description")
    priority = request.form.get("priority", "medium")
    due_date = request.form.get("due_date")
    assigned_to_id = request.form.get("assigned_to_id")
    
    # Verify the thesis is supervised by the current user
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        return redirect(url_for(ep('dashboard')))
    
    # Convert due_date string to timestamp if provided
    due_date_timestamp = None
    if due_date:
        try:
            due_date_obj = datetime.strptime(due_date, '%Y-%m-%d')
            due_date_timestamp = int(due_date_obj.timestamp())
        except ValueError:
            pass
    
    new_todo = Todo(
        thesis_id=thesis_id,
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
    
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/toggle_todo/<int:todo_id>", methods=["POST"])
@login_required
def toggle_todo(todo_id):
    """
    Toggle todo completion status
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Get the todo item and verify access
    todo = Todo.query.join(Thesis).join(Thesis_Supervisor).filter(
        Todo.id == todo_id,
        Thesis_Supervisor.supervisor_id == current_user.id  # Supervisor can access their supervised thesis todos
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
    
    return redirect(url_for('supervisor.dashboard'))


@supervisor.route("/supervisor/delete_todo/<int:todo_id>", methods=["POST"])
@login_required
def delete_todo(todo_id):
    """
    Delete a todo item
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Get the todo item and verify access (only author or supervisor can delete)
    todo = Todo.query.join(Thesis).join(Thesis_Supervisor).filter(
        Todo.id == todo_id,
        (Todo.author_id == current_user.id) |  # Author can delete
        (Thesis_Supervisor.supervisor_id == current_user.id)  # Supervisor can delete
    ).first()
    
    if todo:
        db.session.delete(todo)
        db.session.commit()
    
    return redirect(url_for('supervisor.dashboard'))


@supervisor.route("/supervisor/todo/<int:todo_id>")
@login_required
def todo_detail(todo_id):
    """
    Display todo detail with linked updates and references
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Get the todo first
    todo = Todo.query.get_or_404(todo_id)
    
    # Verify supervisor has access to this todo's thesis
    thesis_supervisor = Thesis_Supervisor.query.filter(
        Thesis_Supervisor.thesis_id == todo.thesis_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("Todo not found or access denied")
        return redirect(url_for('supervisor.dashboard'))
    
    # Get associated updates that reference this todo
    from superviseme.models import Todo_Reference
    referenced_updates = db.session.query(Thesis_Update).join(Todo_Reference).filter(
        Todo_Reference.todo_id == todo_id
    ).order_by(Thesis_Update.created_at.desc()).all()
    
    return render_template("supervisor/todo_detail.html", todo=todo, 
                           referenced_updates=referenced_updates, 
                           dt=datetime.fromtimestamp)


@supervisor.route("/supervisor/add_resource", methods=["POST"])
@login_required
def add_resource():
    """
    Allow supervisors to add resources to supervised theses
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    resource_type = request.form.get("resource_type")
    resource_url = request.form.get("resource_url")
    description = request.form.get("description")
    
    # Verify supervisor has access to this thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("Thesis not found or not supervised by you")
        return redirect(url_for('supervisor.dashboard'))
    
    resource_url = normalize_resource_url(resource_url)
    if not resource_url:
        flash("Please provide a valid http(s) link.")
        return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))
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
    
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


@supervisor.route("/supervisor/add_objective", methods=["POST"])
@login_required
def add_objective():
    """
    Allow supervisors to add objectives to supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    description = request.form.get("description")
    
    # Verify supervisor has access to this thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("Thesis not found or not supervised by you")
        return redirect(url_for(ep('dashboard')))
    
    new_objective = Thesis_Objective(
        thesis_id=thesis_id,
        author_id=current_user.id,
        title=title,
        description=description,
        created_at=int(time.time())
    )
    
    db.session.add(new_objective)
    db.session.commit()
    flash("Objective added successfully")
    
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/edit_objective/<int:objective_id>", methods=["POST"])
@login_required
def edit_objective(objective_id):
    """
    Allow supervisors to edit objectives in supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this objective
    objective = Thesis_Objective.query.join(
        Thesis_Supervisor, Thesis_Objective.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Thesis_Objective.id == objective_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not objective:
        flash("Objective not found or not accessible")
        return redirect(url_for(ep('dashboard')))
    
    objective.title = request.form.get("title", objective.title)
    objective.description = request.form.get("description", objective.description)
    
    db.session.commit()
    flash("Objective updated successfully")
    
    return redirect(url_for(ep('thesis_detail'), thesis_id=objective.thesis_id))


@supervisor.route("/supervisor/add_hypothesis", methods=["POST"])
@login_required
def add_hypothesis():
    """
    Allow supervisors to add hypotheses to supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    description = request.form.get("description")
    
    # Verify supervisor has access to this thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("Thesis not found or not supervised by you")
        return redirect(url_for(ep('dashboard')))
    
    new_hypothesis = Thesis_Hypothesis(
        thesis_id=thesis_id,
        author_id=current_user.id,
        title=title,
        description=description,
        created_at=int(time.time())
    )
    
    db.session.add(new_hypothesis)
    db.session.commit()
    flash("Hypothesis added successfully")
    
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/edit_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def edit_hypothesis(hypothesis_id):
    """
    Allow supervisors to edit hypotheses in supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this hypothesis
    hypothesis = Thesis_Hypothesis.query.join(
        Thesis_Supervisor, Thesis_Hypothesis.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Thesis_Hypothesis.id == hypothesis_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not hypothesis:
        flash("Hypothesis not found or not accessible")
        return redirect(url_for(ep('dashboard')))
    
    hypothesis.title = request.form.get("title", hypothesis.title)
    hypothesis.description = request.form.get("description", hypothesis.description)
    
    db.session.commit()
    flash("Hypothesis updated successfully")
    
    return redirect(url_for(ep('thesis_detail'), thesis_id=hypothesis.thesis_id))


@supervisor.route("/supervisor/delete_objective/<int:objective_id>", methods=["POST", "DELETE"])
@login_required
def delete_objective(objective_id):
    """
    Allow supervisors to delete objectives from supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this objective
    objective = Thesis_Objective.query.join(
        Thesis_Supervisor, Thesis_Objective.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Thesis_Objective.id == objective_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not objective:
        flash("Objective not found or not accessible")
        return redirect(url_for(ep('dashboard')))
    
    thesis_id = objective.thesis_id
    db.session.delete(objective)
    db.session.commit()
    flash("Objective deleted successfully")
    
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/delete_hypothesis/<int:hypothesis_id>", methods=["POST", "DELETE"])
@login_required
def delete_hypothesis(hypothesis_id):
    """
    Allow supervisors to delete hypotheses from supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this hypothesis
    hypothesis = Thesis_Hypothesis.query.join(
        Thesis_Supervisor, Thesis_Hypothesis.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Thesis_Hypothesis.id == hypothesis_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not hypothesis:
        flash("Hypothesis not found or not accessible")
        return redirect(url_for(ep('dashboard')))
    
    thesis_id = hypothesis.thesis_id
    db.session.delete(hypothesis)
    db.session.commit()
    flash("Hypothesis deleted successfully")
    
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/edit_resource/<int:resource_id>", methods=["POST"])
@login_required
def edit_resource(resource_id):
    """
    Allow supervisors to edit resources in supervised theses
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this resource
    resource = Resource.query.join(
        Thesis_Supervisor, Resource.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Resource.id == resource_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not resource:
        flash("Resource not found or not accessible")
        return redirect(url_for('supervisor.dashboard'))
    
    new_url = normalize_resource_url(request.form.get("resource_url", resource.resource_url))
    if not new_url:
        flash("Please provide a valid http(s) link.")
        return redirect(url_for('supervisor.thesis_detail', thesis_id=resource.thesis_id))
    resource.resource_url = new_url
    resource.resource_type = resolve_resource_type(request.form.get("resource_type", resource.resource_type), new_url)
    resource.description = request.form.get("description", resource.description)
    
    db.session.commit()
    flash("Resource updated successfully")
    
    return redirect(url_for('supervisor.thesis_detail', thesis_id=resource.thesis_id))


@supervisor.route("/supervisor/delete_resource/<int:resource_id>", methods=["POST", "DELETE"])
@login_required
def delete_resource(resource_id):
    """
    Allow supervisors to delete resources from supervised theses
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this resource
    resource = Resource.query.join(
        Thesis_Supervisor, Resource.thesis_id == Thesis_Supervisor.thesis_id
    ).filter(
        Resource.id == resource_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not resource:
        flash("Resource not found or not accessible")
        return redirect(url_for('supervisor.dashboard'))
    
    thesis_id = resource.thesis_id
    db.session.delete(resource)
    db.session.commit()
    flash("Resource deleted successfully")
    
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


# Meeting Notes routes for supervisors
@supervisor.route("/supervisor/add_meeting_note", methods=["POST"])
@login_required
def add_meeting_note():
    """
    Allow supervisors to add meeting notes to supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    content = request.form.get("content")
    
    # Verify supervisor has access to this thesis
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        flash("Thesis not found or not supervised by you")
        return redirect(url_for(ep('dashboard')))
    
    current_time = int(time.time())
    new_meeting_note = MeetingNote(
        thesis_id=thesis_id,
        author_id=current_user.id,
        title=title,
        content=content,
        created_at=current_time,
        updated_at=current_time
    )
    
    db.session.add(new_meeting_note)
    db.session.flush()  # This assigns the ID without committing the transaction
    
    # Get the ID immediately after flush
    meeting_note_id = new_meeting_note.id
    
    db.session.commit()
    
    # Parse and create todo references
    from superviseme.utils.todo_parser import parse_todo_references, create_meeting_note_todo_references
    todo_refs = parse_todo_references(content)
    if todo_refs:
        create_meeting_note_todo_references(meeting_note_id, todo_refs)
    
    flash("Meeting note added successfully")
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))


@supervisor.route("/supervisor/edit_meeting_note/<int:note_id>", methods=["POST"])
@login_required
def edit_meeting_note(note_id):
    """
    Allow supervisors to edit meeting notes in supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this meeting note
    meeting_note = MeetingNote.query.join(Thesis, MeetingNote.thesis_id == Thesis.id)\
                                   .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)\
                                   .filter(MeetingNote.id == note_id,
                                          Thesis_Supervisor.supervisor_id == current_user.id)\
                                   .first()
    
    if not meeting_note:
        flash("Meeting note not found or not accessible")
        return redirect(url_for(ep('dashboard')))
    
    meeting_note.title = request.form.get("title", meeting_note.title)
    meeting_note.content = request.form.get("content", meeting_note.content)
    meeting_note.updated_at = int(time.time())
    
    # Get the ID before any potential session changes
    meeting_note_id = meeting_note.id
    
    db.session.commit()
    
    # Update todo references
    from superviseme.utils.todo_parser import parse_todo_references, create_meeting_note_todo_references
    todo_refs = parse_todo_references(meeting_note.content)
    create_meeting_note_todo_references(meeting_note_id, todo_refs)
    
    flash("Meeting note updated successfully")
    return redirect(url_for(ep('thesis_detail'), thesis_id=meeting_note.thesis_id))


@supervisor.route("/supervisor/meeting_note/<int:note_id>")
@login_required
def meeting_note_detail(note_id):
    """
    Display detailed view of a meeting note with full CRUD capabilities
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this meeting note
    meeting_note = MeetingNote.query.join(Thesis, MeetingNote.thesis_id == Thesis.id)\
                                   .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)\
                                   .filter(MeetingNote.id == note_id,
                                          Thesis_Supervisor.supervisor_id == current_user.id)\
                                   .first()
    
    if not meeting_note:
        flash("Meeting note not found or not accessible")
        return redirect(url_for('supervisor.dashboard'))
    
    # Get thesis information for context
    thesis = meeting_note.thesis
    
    # Get todos for this thesis for reference dropdown
    todos = Todo.query.filter_by(thesis_id=thesis.id).order_by(Todo.created_at.desc()).all()
    
    return render_template("supervisor/meeting_note_detail.html", 
                         meeting_note=meeting_note, 
                         thesis=thesis,
                         todos=todos,
                         dt=datetime.fromtimestamp)


@supervisor.route("/supervisor/delete_meeting_note/<int:note_id>", methods=["POST"])
@login_required
def delete_meeting_note(note_id):
    """
    Allow supervisors to delete meeting notes from supervised theses
    """
    privilege_check = supervision_gate()
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this meeting note
    meeting_note = MeetingNote.query.join(Thesis, MeetingNote.thesis_id == Thesis.id)\
                                   .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)\
                                   .filter(MeetingNote.id == note_id,
                                          Thesis_Supervisor.supervisor_id == current_user.id)\
                                   .first()
    
    if not meeting_note:
        flash("Meeting note not found or not accessible")
        return redirect(url_for(ep('dashboard')))
    
    thesis_id = meeting_note.thesis_id
    db.session.delete(meeting_note)
    db.session.commit()
    
    flash("Meeting note deleted successfully")
    return redirect(url_for(ep('thesis_detail'), thesis_id=thesis_id))
