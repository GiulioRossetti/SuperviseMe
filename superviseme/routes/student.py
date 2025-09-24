from flask import Blueprint, request, render_template, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from sqlalchemy import and_, or_
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils.activity_tracker import update_user_activity
from superviseme.models import *
from superviseme import db
from datetime import datetime
import time

student = Blueprint("student", __name__)


@student.route("/student/dashboard")
@login_required
def dashboard():
    """
    This route is for student dashboard. It shows the student's thesis information,
    updates, and progress.
    """
    check_privileges(current_user.username, role="student")
    
    # Update user activity
    update_user_activity("student_dashboard")
    
    # Get the student's thesis
    thesis = Thesis.query.filter_by(author_id=current_user.id).first()
    
    # Get statistics
    thesis_stats = {}
    if thesis:
        thesis_stats = {
            'updates_count': Thesis_Update.query.filter_by(
                thesis_id=thesis.id, 
                author_id=current_user.id
            ).count(),
            'supervisor_comments': Thesis_Update.query.filter_by(
                thesis_id=thesis.id, 
                update_type='supervisor_update'
            ).count(),
            'resources_count': Resource.query.filter_by(thesis_id=thesis.id).count(),
        }
        
        # Get recent updates
        recent_updates = Thesis_Update.query.filter_by(
            thesis_id=thesis.id
        ).order_by(Thesis_Update.created_at.desc()).limit(5).all()
        
        # Get todos for the thesis
        todos = Todo.query.filter_by(thesis_id=thesis.id).order_by(
            Todo.status.asc(),  # pending first
            Todo.priority.desc(),  # high priority first
            Todo.created_at.desc()
        ).all()
        
        # Get supervisor info for todo assignment
        supervisor_info = None
        thesis_supervisor = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).first()
        if thesis_supervisor:
            supervisor_info = thesis_supervisor.supervisor
    else:
        thesis_stats = {
            'updates_count': 0,
            'supervisor_comments': 0,
            'resources_count': 0,
        }
        recent_updates = []
        todos = []
        supervisor_info = None
        
    return render_template("student/student_dashboard.html", 
                         thesis=thesis, 
                         thesis_stats=thesis_stats,
                         recent_updates=recent_updates,
                         todos=todos,
                         supervisor_info=supervisor_info,
                         dt=datetime.fromtimestamp)


@student.route("/thesis")
@login_required
def thesis_data():
    """
    This route is for thesis data. It retrieves the student's thesis and related data
    and renders them in a template.
    """
    check_privileges(current_user.username, role="student")
    
    # Get student's thesis
    thesis = Thesis.query.filter_by(author_id=current_user.id).first()
    
    if not thesis:
        return render_template("student/no_thesis.html")
    
    # Get supervisors for this thesis
    thesis_supervisors = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()
    supervisors = [ts.supervisor for ts in thesis_supervisors]
    
    # Get thesis tags
    tags = Thesis_Tag.query.filter_by(thesis_id=thesis.id).all()
    
    # Get all updates for this thesis, organized for threaded display
    # Get parent updates (top-level updates with no parent_id)
    parent_updates = Thesis_Update.query.filter_by(
        thesis_id=thesis.id, 
        parent_id=None
    ).order_by(Thesis_Update.created_at.desc()).all()
    
    # Get all comments/replies
    all_comments = Thesis_Update.query.filter(
        Thesis_Update.thesis_id == thesis.id,
        Thesis_Update.parent_id.isnot(None)
    ).order_by(Thesis_Update.created_at.asc()).all()
    
    # Group comments by parent_id
    comments_by_parent = {}
    for comment in all_comments:
        if comment.parent_id not in comments_by_parent:
            comments_by_parent[comment.parent_id] = []
        comments_by_parent[comment.parent_id].append(comment)
    
    # Also get all updates for backwards compatibility (if needed elsewhere)
    updates = Thesis_Update.query.filter_by(thesis_id=thesis.id).order_by(Thesis_Update.created_at.desc()).all()
    
    # Get resources
    resources = Resource.query.filter_by(thesis_id=thesis.id).all()
    
    # Get objectives and hypotheses
    objectives = Thesis_Objective.query.filter_by(thesis_id=thesis.id).order_by(Thesis_Objective.created_at.desc()).all()
    hypotheses = Thesis_Hypothesis.query.filter_by(thesis_id=thesis.id).order_by(Thesis_Hypothesis.created_at.desc()).all()
    
    # Get todos
    todos = Todo.query.filter_by(thesis_id=thesis.id).order_by(Todo.created_at.desc()).all()
    
    # Get meeting notes
    meeting_notes = MeetingNote.query.filter_by(thesis_id=thesis.id).order_by(MeetingNote.created_at.desc()).all()
    
    # Get thesis status history
    thesis_statuses = Thesis_Status.query.filter_by(thesis_id=thesis.id).order_by(Thesis_Status.updated_at.desc()).all()
    
    return render_template("student/thesis.html", thesis=thesis, supervisors=supervisors,
                           tags=tags, updates=updates, parent_updates=parent_updates,
                           comments_by_parent=comments_by_parent, resources=resources, 
                           objectives=objectives, hypotheses=hypotheses, todos=todos, 
                           meeting_notes=meeting_notes, thesis_statuses=thesis_statuses, dt=datetime.fromtimestamp)


@student.route("/post_update", methods=["POST"])
@login_required
def post_update():
    """
    This route handles posting updates to a thesis. It retrieves the necessary data from the form,
    creates a new Update object, and saves it to the database.
    """
    check_privileges(current_user.username, role="student")
    
    # Update user activity
    update_user_activity("posting_thesis_update")
    
    thesis_id = request.form.get("thesis_id")
    content = request.form.get("content")
    
    # Verify the thesis belongs to the current student
    thesis = Thesis.query.filter_by(id=thesis_id, author_id=current_user.id).first()
    if not thesis:
        return redirect(url_for('student.thesis_data'))

    new_update = Thesis_Update(
        thesis_id=thesis_id,
        author_id=current_user.id,
        content=content,
        update_type="student_update",
        created_at=int(time.time())
    )

    db.session.add(new_update)
    db.session.commit()

    # Parse and create todo references
    from superviseme.utils.todo_parser import parse_todo_references, create_todo_references
    todo_refs = parse_todo_references(content)
    if todo_refs:
        create_todo_references(new_update.id, todo_refs)

    # Create notification for supervisors
    from superviseme.utils.notifications import create_thesis_update_notification
    create_thesis_update_notification(thesis_id, current_user.id, content)

    return redirect(url_for('student.thesis_data'))


@student.route("/post_comment", methods=["POST"])
@login_required
def post_comment():
    """
    This route handles posting comments on updates. It retrieves the necessary data from the form,
    creates a new Update object with the comment, and saves it to the database.
    """
    check_privileges(current_user.username, role="student")
    
    update_id = request.form.get("update_id")
    content = request.form.get("content")
    thesis_id = request.form.get("thesis_id")
    
    # Verify the thesis belongs to the current student
    thesis = Thesis.query.filter_by(id=thesis_id, author_id=current_user.id).first()
    if not thesis:
        return redirect(url_for('student.thesis_data'))

    new_comment = Thesis_Update(
        thesis_id=thesis_id,
        author_id=current_user.id,
        content=content,
        update_type="student_comment",
        parent_id=update_id,  # Link to the original update
        created_at=int(time.time())
    )

    db.session.add(new_comment)
    db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/delete_update/<int:update_id>")
@login_required
def delete_update(update_id):
    """
    This route handles deleting an update. It retrieves the update by its ID,
    deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="student")
    
    # Verify the update belongs to the current student
    update = Thesis_Update.query.filter_by(
        id=update_id, 
        author_id=current_user.id,
        update_type="student_update"
    ).first()
    
    if update:
        db.session.delete(update)
        db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/delete_comment/<int:comment_id>")
@login_required
def delete_comment(comment_id):
    """
    This route handles deleting a comment. It retrieves the comment by its ID,
    deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="student")
    
    # Verify the comment belongs to the current student
    comment = Thesis_Update.query.filter_by(
        id=comment_id,
        author_id=current_user.id,
        update_type="student_comment"
    ).first()
    
    if comment:
        db.session.delete(comment)
        db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/modify_comment", methods=["POST"])
@login_required
def modify_comment():
    """
    This route handles modifying a comment. It retrieves the necessary data from the form,
    updates the comment in the database, and commits the changes.
    """
    check_privileges(current_user.username, role="student")
    
    comment_id = request.form.get("comment_id")
    new_content = request.form.get("new_content")

    # Verify the comment belongs to the current student
    comment = Thesis_Update.query.filter_by(
        id=comment_id,
        author_id=current_user.id,
        update_type="student_comment"
    ).first()
    
    if comment:
        comment.content = new_content
        db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/modify_update", methods=["POST"])
@login_required
def modify_update():
    """
    This route handles modifying an update. It retrieves the necessary data from the form,
    updates the update in the database, and commits the changes.
    """
    check_privileges(current_user.username, role="student")
    
    # Update user activity
    update_user_activity("modifying_thesis_update")
    
    update_id = request.form.get("update_id")
    new_content = request.form.get("new_content")

    # Verify the update belongs to the current student
    update = Thesis_Update.query.filter_by(
        id=update_id, 
        author_id=current_user.id,
        update_type="student_update"
    ).first()
    
    if update:
        update.content = new_content
        db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/tag_update", methods=["POST"])
@login_required
def tag_update():
    """
    This route handles tagging an update. It retrieves the necessary data from the form,
    creates a new Update_Tag object, and saves it to the database.
    """
    check_privileges(current_user.username, role="student")
    
    update_id = request.form.get("update_id")
    tag = request.form.get("tag")

    # Verify the update belongs to the current student
    update = Thesis_Update.query.filter_by(
        id=update_id,
        author_id=current_user.id,
        update_type="student_update"
    ).first()
    
    if update:
        new_tag = Update_Tag(
            update_id=update_id,
            tag=tag
        )

        db.session.add(new_tag)
        db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/remove_update_tag", methods=["POST"])
@login_required
def remove_update_tag():
    """
    This route handles removing a tag from an update. It retrieves the necessary data from the form,
    finds the Update_Tag object, deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="student")
    
    update_id = request.form.get("update_id")
    tag = request.form.get("tag")

    # Verify the update belongs to the current student before removing tag
    update = Thesis_Update.query.filter_by(
        id=update_id,
        author_id=current_user.id,
        update_type="student_update"
    ).first()
    
    if update:
        update_tag = Update_Tag.query.filter_by(update_id=update_id, tag=tag).first()
        if update_tag:
            db.session.delete(update_tag)
            db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/add_resource", methods=["POST"])
@login_required
def add_resource():
    """
    This route handles adding a resource to a thesis. It retrieves the necessary data from the form,
    creates a new Resource object, and saves it to the database.
    """
    check_privileges(current_user.username, role="student")
    
    thesis_id = request.form.get("thesis_id")
    resource_type = request.form.get("resource_type")
    resource_url = request.form.get("resource_link")  # Form uses resource_link but model uses resource_url
    description = request.form.get("description")
    
    # Verify the thesis belongs to the current student
    thesis = Thesis.query.filter_by(id=thesis_id, author_id=current_user.id).first()
    if not thesis:
        return redirect(url_for('student.thesis_data'))

    new_resource = Resource(
        thesis_id=thesis_id,
        resource_type=resource_type,
        resource_url=resource_url,
        description=description,
        created_at=int(time.time())
    )

    db.session.add(new_resource)
    db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/delete_resource/<int:resource_id>")
@login_required
def delete_resource(resource_id):
    """
    This route handles deleting a resource. It retrieves the resource by its ID,
    deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="student")
    
    # Verify the resource belongs to a thesis owned by the current student
    resource = Resource.query.join(Thesis).filter(
        Resource.id == resource_id,
        Thesis.author_id == current_user.id
    ).first()
    
    if resource:
        db.session.delete(resource)
        db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/add_objective", methods=["POST"])
@login_required
def add_objective():
    """
    This route handles adding an objective to a thesis. It retrieves the necessary data from the form,
    creates a new Thesis_Objective object, and saves it to the database.
    """
    check_privileges(current_user.username, role="student")
    
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    description = request.form.get("description")
    
    # Verify the thesis belongs to the current student
    thesis = Thesis.query.filter_by(id=thesis_id, author_id=current_user.id).first()
    if not thesis:
        return redirect(url_for('student.thesis_data'))

    new_objective = Thesis_Objective(
        thesis_id=thesis_id,
        author_id=current_user.id,
        title=title,
        description=description,
        created_at=int(time.time())
    )

    db.session.add(new_objective)
    db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/delete_objective/<int:objective_id>")
@login_required
def delete_objective(objective_id):
    """
    This route handles deleting an objective. It retrieves the objective by its ID,
    deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="student")
    
    # Verify the objective belongs to the current student
    objective = Thesis_Objective.query.filter_by(
        id=objective_id,
        author_id=current_user.id
    ).first()
    
    if objective and not objective.frozen:
        db.session.delete(objective)
        db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/add_hypothesis", methods=["POST"])
@login_required
def add_hypothesis():
    """
    This route handles adding a hypothesis to a thesis. It retrieves the necessary data from the form,
    creates a new Thesis_Hypothesis object, and saves it to the database.
    """
    check_privileges(current_user.username, role="student")
    
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    description = request.form.get("description")
    
    # Verify the thesis belongs to the current student
    thesis = Thesis.query.filter_by(id=thesis_id, author_id=current_user.id).first()
    if not thesis:
        return redirect(url_for('student.thesis_data'))

    new_hypothesis = Thesis_Hypothesis(
        thesis_id=thesis_id,
        author_id=current_user.id,
        title=title,
        description=description,
        created_at=int(time.time())
    )

    db.session.add(new_hypothesis)
    db.session.commit()

    return redirect(url_for('student.thesis_data'))


@student.route("/delete_hypothesis/<int:hypothesis_id>")
@login_required
def delete_hypothesis(hypothesis_id):
    """
    This route handles deleting a hypothesis. It retrieves the hypothesis by its ID,
    deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="student")
    
    # Verify the hypothesis belongs to the current student
    hypothesis = Thesis_Hypothesis.query.filter_by(
        id=hypothesis_id,
        author_id=current_user.id
    ).first()
    
    if hypothesis and not hypothesis.frozen:
        db.session.delete(hypothesis)
        db.session.commit()

    return redirect(url_for('student.thesis_data'))


# Todo routes for students
@student.route("/add_todo", methods=["POST"])
@login_required
def add_todo():
    """
    Add a new todo item to the student's thesis
    """
    check_privileges(current_user.username, role="student")
    
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    description = request.form.get("description")
    priority = request.form.get("priority", "medium")
    due_date = request.form.get("due_date")
    assigned_to_id = request.form.get("assigned_to_id")
    
    # Verify the thesis belongs to the current student
    thesis = Thesis.query.filter_by(id=thesis_id, author_id=current_user.id).first()
    if not thesis:
        return redirect(url_for('student.dashboard'))
    
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
    
    return redirect(url_for('student.thesis_data'))


@student.route("/toggle_todo/<int:todo_id>")
@login_required
def toggle_todo(todo_id):
    """
    Toggle todo completion status
    """
    check_privileges(current_user.username, role="student")
    
    # Get the todo item and verify access
    todo = Todo.query.join(Thesis).filter(
        Todo.id == todo_id,
        (Thesis.author_id == current_user.id)  # Student can access their thesis todos
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
    
    return redirect(url_for('student.dashboard'))


@student.route("/student/search", methods=["POST"])
@login_required
def search():
    """
    Handle search requests from student interface.
    Search within student's thesis context.
    """
    check_privileges(current_user.username, role="student")
    
    search_term = request.form.get("search_term", "").strip()
    
    # Validate search term
    if not search_term:
        # If no search term, redirect back to dashboard with message
        from flask import flash, redirect, url_for
        flash("Please enter a search term.", "warning")
        return redirect(url_for('student.student_dashboard'))
    
    # Get student's thesis
    thesis = Thesis.query.filter_by(author_id=current_user.id).first()
    
    # Search for updates and resources within student's thesis
    updates = []
    resources = []
    todos = []
    
    if search_term and thesis:
        # Search in thesis updates
        updates = Thesis_Update.query.filter(
            and_(
                Thesis_Update.thesis_id == thesis.id,
                or_(
                    Thesis_Update.content.ilike(f"%{search_term}%"),
                    Thesis_Update.update_type.ilike(f"%{search_term}%")
                )
            )
        ).all()
        
        # Search in thesis resources
        resources = Resource.query.filter(
            and_(
                Resource.thesis_id == thesis.id,
                or_(
                    Resource.name.ilike(f"%{search_term}%"),
                    Resource.url.ilike(f"%{search_term}%")
                )
            )
        ).all()
        
        # Search in todos
        todos = Todo.query.filter(
            and_(
                Todo.thesis_id == thesis.id,
                or_(
                    Todo.title.ilike(f"%{search_term}%"),
                    Todo.description.ilike(f"%{search_term}%")
                )
            )
        ).all()
    
    return render_template("student/search_results.html", 
                         updates=updates, 
                         resources=resources, 
                         todos=todos,
                         thesis=thesis,
                         search_term=search_term,
                         user_type="student",
                         dt=datetime.fromtimestamp)


@student.route("/student/todo/<int:todo_id>")
@login_required
def todo_detail(todo_id):
    """
    Display todo detail with linked updates and references for student
    """
    check_privileges(current_user.username, role="student")
    
    # Get the todo and verify access (must be from student's thesis)
    todo = Todo.query.join(Thesis, Todo.thesis_id == Thesis.id).filter(
        Todo.id == todo_id,
        Thesis.author_id == current_user.id  # Student can access their thesis todos
    ).first()
    
    if not todo:
        flash("Todo not found or access denied")
        return redirect(url_for('student.dashboard'))
    
    # Get associated updates that reference this todo
    from superviseme.models import Todo_Reference
    referenced_updates = db.session.query(Thesis_Update).join(Todo_Reference).filter(
        Todo_Reference.todo_id == todo_id
    ).order_by(Thesis_Update.created_at.desc()).all()
    
    return render_template("student/todo_detail.html", todo=todo, 
                           referenced_updates=referenced_updates, 
                           dt=datetime.fromtimestamp)


@student.route("/delete_todo/<int:todo_id>")
@login_required
def delete_todo(todo_id):
    """
    Delete a todo item
    """
    check_privileges(current_user.username, role="student")
    
    # Get the todo item and verify access (only author can delete)
    todo = Todo.query.join(Thesis).filter(
        Todo.id == todo_id,
        Todo.author_id == current_user.id,  # Only author can delete
        Thesis.author_id == current_user.id  # Student's thesis
    ).first()
    
    if todo:
        db.session.delete(todo)
        db.session.commit()
    
    return redirect(url_for('student.thesis_data'))


# Meeting Notes routes for students
@student.route("/add_meeting_note", methods=["POST"])
@login_required
def add_meeting_note():
    """
    Allow students to add meeting notes to their thesis
    """
    check_privileges(current_user.username, role="student")
    
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    content = request.form.get("content")
    
    # Verify the thesis belongs to the current student
    thesis = Thesis.query.filter_by(id=thesis_id, author_id=current_user.id).first()
    if not thesis:
        flash("Thesis not found or access denied")
        return redirect(url_for('student.dashboard'))
    
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
    return redirect(url_for('student.thesis_data'))


@student.route("/edit_meeting_note/<int:note_id>", methods=["POST"])
@login_required
def edit_meeting_note(note_id):
    """
    Allow students to edit their meeting notes
    """
    check_privileges(current_user.username, role="student")
    
    # Verify student has access to this meeting note
    meeting_note = MeetingNote.query.join(Thesis).filter(
        MeetingNote.id == note_id,
        Thesis.author_id == current_user.id
    ).first()
    
    if not meeting_note:
        flash("Meeting note not found or not accessible")
        return redirect(url_for('student.dashboard'))
    
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
    return redirect(url_for('student.thesis_data'))


@student.route("/delete_meeting_note/<int:note_id>", methods=["POST"])
@login_required
def delete_meeting_note(note_id):
    """
    Allow students to delete their meeting notes
    """
    check_privileges(current_user.username, role="student")
    
    # Verify student has access to this meeting note
    meeting_note = MeetingNote.query.join(Thesis).filter(
        MeetingNote.id == note_id,
        Thesis.author_id == current_user.id
    ).first()
    
    if not meeting_note:
        flash("Meeting note not found or not accessible")
        return redirect(url_for('student.dashboard'))
    
    db.session.delete(meeting_note)
    db.session.commit()
    
    flash("Meeting note deleted successfully")
    return redirect(url_for('student.thesis_data'))