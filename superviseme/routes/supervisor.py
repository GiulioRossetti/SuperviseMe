from flask import Blueprint, request, render_template, abort, redirect, url_for, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, and_, func, or_
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils.activity_tracker import get_inactive_students
from superviseme.models import *
from superviseme import db
from datetime import datetime
import time

supervisor = Blueprint("supervisor", __name__)


@supervisor.route("/supervisor/dashboard")
@login_required
def dashboard():
    """
    This route is for admin data. It retrieves all users from the database
    and renders them in a template.
    """
    check_privileges(current_user.username, role="supervisor")

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


    # for each supervisor get list of theses assigned to them along with the name of the student

    theses = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    theses_by_supervisor = [
                    {
                        "thesis": Thesis.query.filter(Thesis.id == thesis.id, Thesis.author_id.isnot(None)).first(),
                        "student": db.session.execute(
                                    select(User_mgmt)
                                    .join(Thesis, Thesis.author_id == User_mgmt.id)
                                    .where(
                                        and_(Thesis.id == thesis.id, Thesis.author_id.isnot(None))
                                    )
                                ).scalars().first()
                    } for thesis in theses

                ]
    # filter out theses that have no student assigned
    theses_by_supervisor =  [t for t in theses_by_supervisor if t["student"] is not None ]

    available_theses_by_supervisor = db.session.execute(
            select(Thesis)
            .join(Thesis_Supervisor, Thesis.id == Thesis_Supervisor.thesis_id)
            .where(Thesis_Supervisor.supervisor_id == current_user.id, Thesis.author_id.is_(None))

        ).scalars().all()

    # Get todos for supervised theses
    supervised_thesis_ids = [ts.thesis_id for ts in theses]
    todos = []
    students_info = {}
    if supervised_thesis_ids:
        todos = Todo.query.filter(Todo.thesis_id.in_(supervised_thesis_ids)).order_by(
            Todo.status.asc(),  # pending first
            Todo.priority.desc(),  # high priority first
            Todo.created_at.desc()
        ).all()
        
        # Get student information for each thesis
        for ts in theses_by_supervisor:
            if ts["student"]:
                students_info[ts["thesis"].id] = ts["student"]

    return render_template("/supervisor/supervisor_dashboard.html", current_user=current_user,
                           user_counts=user_counts, thesis_counts=thesis_counts,
                           theses_by_supervisor=theses_by_supervisor, available_theses=available_theses_by_supervisor, 
                           todos=todos, students_info=students_info, dt=datetime.fromtimestamp, str=str)

@supervisor.route("/supervisee")
@login_required
def supervisee_data():
    """
    This route is for supervisee data. It retrieves all supervisees from the database
    and renders them in a template.
    """
    check_privileges(current_user.username, role="supervisor")
    
    # Get students through thesis supervision relationship
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    supervisees = []
    
    # Get inactive students data
    inactive_data = get_inactive_students(current_user.id)
    inactive_dict = {data['student'].id: data for data in inactive_data}
    
    for ts in thesis_supervisors:
        if ts.thesis and ts.thesis.author:
            student_data = inactive_dict.get(ts.thesis.author.id, {})
            supervisees.append({
                'student': ts.thesis.author,
                'thesis': ts.thesis,
                'is_inactive': student_data.get('is_inactive', False),
                'days_inactive': student_data.get('days_inactive'),
                'last_activity_location': student_data.get('last_activity_location')
            })
    
    return render_template("supervisor/supervisees.html", supervisees=supervisees)


@supervisor.route("/theses")
@login_required
def theses_data():
    """
    This route is for thesis data. It retrieves all theses supervised by the current user
    and renders them in a template.
    """
    check_privileges(current_user.username, role="supervisor")
    
    # Get theses through the supervisor relationship
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    theses = [ts.thesis for ts in thesis_supervisors]
    return render_template("supervisor/theses.html", theses=theses, dt=datetime.fromtimestamp)


@supervisor.route("/thesis/<thesis_id>")
@login_required
def thesis_detail(thesis_id):
    """
    This route retrieves details of a specific thesis by its ID and renders them in a template.
    """
    check_privileges(current_user.username, role="supervisor")
    
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
    resources = Resource.query.filter_by(thesis_id=thesis_id).all()
    
    # Get objectives and hypotheses
    objectives = Thesis_Objective.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Objective.created_at.desc()).all()
    hypotheses = Thesis_Hypothesis.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Hypothesis.created_at.desc()).all()

    return render_template("supervisor/thesis_detail.html", thesis=thesis, updates=updates,
                           supervisors=supervisors, author=author, objectives=objectives, 
                           hypotheses=hypotheses, thesis_tags=thesis_tags, resources=resources, 
                           dt=datetime.fromtimestamp)


@supervisor.route("/post_update", methods=["POST"])
@login_required
def post_update():
    """
    This route handles posting updates to a thesis. It retrieves the necessary data from the form,
    creates a new Update object, and saves it to the database.
    """
    thesis_id = request.form.get("thesis_id")
    content = request.form.get("content")

    new_update = Thesis_Update(
        thesis_id=thesis_id,
        author_id=current_user.id,
        content=content,
        update_type="supervisor_update",
        created_at=int(time.time())
    )

    db.session.add(new_update)
    db.session.commit()

    return thesis_detail(thesis_id)


@supervisor.route("/post_comment", methods=["POST"])
@login_required
def post_comment():
    """
    This route handles posting comments on updates. It retrieves the necessary data from the form,
    creates a new Update object with the comment, and saves it to the database.
    """
    update_id = request.form.get("update_id")
    content = request.form.get("content")

    new_comment = Thesis_Update(
        update_id=update_id,
        author_id=current_user.id,
        content=content,
        update_type="supervisor_comment",
        created_at=int(time.time())
    )

    db.session.add(new_comment)
    db.session.commit()

    return thesis_detail(update_id)


@supervisor.route("/delete_update/<int:update_id>")
@login_required
def delete_update(update_id):
    """
    This route handles deleting an update by its ID. It retrieves the update, deletes it from the database,
    and redirects to the thesis detail page.
    """
    check_privileges(current_user.username, role="supervisor")
    
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
        return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))

    return redirect(url_for('supervisor.theses_data'))


#@supervisor.route("/delete_thesis/<int:thesis_id>")
#@login_required
def delete_thesis(thesis_id):
    """
    This route handles deleting a thesis by its ID. It retrieves the thesis, deletes it from the database,
    and redirects to the theses data page.
    """
    thesis = Thesis.query.get_or_404(thesis_id)
    db.session.delete(thesis)
    db.session.commit()

    return theses_data()


@supervisor.route("/delete_comment", methods=["POST"])
@login_required
def delete_comment():
    """
    This route handles deleting a comment. It retrieves the comment ID from the form,
    deletes the comment from the database, and redirects to the thesis detail page.
    """
    check_privileges(current_user.username, role="supervisor")
    
    comment_id = request.form.get("comment_id")
    
    # Verify the comment belongs to a thesis supervised by the current user
    comment = Thesis_Update.query.join(Thesis_Supervisor).filter(
        Thesis_Update.id == comment_id,
        Thesis_Update.update_type == "supervisor_update",
        Thesis_Update.author_id == current_user.id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if comment:
        thesis_id = comment.thesis_id
        db.session.delete(comment)
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/modify_update", methods=["POST"])
@login_required
def modify_update():
    """
    This route handles modifying an update. It retrieves the necessary data from the form,
    updates the content of the update in the database, and redirects to the thesis detail page.
    """
    check_privileges(current_user.username, role="supervisor")
    
    update_id = request.form.get("update_id")
    new_content = request.form.get("new_content")

    # Verify the update belongs to a thesis supervised by the current user
    update = Thesis_Update.query.join(Thesis_Supervisor).filter(
        Thesis_Update.id == update_id,
        Thesis_Update.update_type == "supervisor_update",
        Thesis_Update.author_id == current_user.id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if update:
        update.content = new_content
        db.session.commit()
        return redirect(url_for('supervisor.thesis_detail', thesis_id=update.thesis_id))

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/modify_comment", methods=["POST"])
@login_required
def modify_comment():
    """
    This route handles modifying a comment. It retrieves the necessary data from the form,
    updates the content of the comment in the database, and redirects to the thesis detail page.
    """
    comment_id = request.form.get("comment_id")
    new_content = request.form.get("new_content")

    comment = Thesis_Update.query.get_or_404(comment_id)
    comment.content = new_content
    db.session.commit()

    return thesis_detail(comment.thesis_id)


@supervisor.route("/tag_thesis", methods=["POST"])
@login_required
def tag_thesis():
    """
    This route handles tagging a thesis. It retrieves the necessary data from the form,
    updates the thesis with the new tags, and redirects to the thesis detail page.
    """
    thesis_id = request.form.get("thesis_id")
    tags = request.form.get("tags")
    for tag in tags:
        new_tag = Update_Tag(
            thesis_id=thesis_id,
            author_id=current_user.id,
            tag=tag,
            created_at=int(time.time())
        )
        db.session.add(new_tag)

    db.session.commit()

    return thesis_detail(thesis_id)


@supervisor.route("/delete_tag", methods=["POST"])
@login_required
def delete_tag():
    """
    This route handles deleting a tag from a thesis. It retrieves the tag ID from the form,
    deletes the tag from the database, and redirects to the thesis detail page.
    """
    tag_id = request.form.get("tag_id")
    tag = Update_Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()

    return thesis_detail(tag.thesis_id)


@supervisor.route("/tag_update", methods=["POST"])
@login_required
def tag_update():
    """
    This route handles tagging an update. It retrieves the necessary data from the form,
    updates the update with the new tags, and redirects to the thesis detail page.
    """
    update_id = request.form.get("update_id")
    tags = request.form.get("tags")
    for tag in tags:
        new_tag = Update_Tag(
            update_id=update_id,
            author_id=current_user.id,
            tag=tag,
            created_at=int(time.time())
        )
        db.session.add(new_tag)

    db.session.commit()

    return thesis_detail(update_id)


@supervisor.route("/delete_update_tag", methods=["POST"])
@login_required
def delete_update_tag():
    """
    This route handles deleting a tag from an update. It retrieves the tag ID from the form,
    deletes the tag from the database, and redirects to the thesis detail page.
    """
    tag_id = request.form.get("tag_id")
    tag = Update_Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()

    return thesis_detail(tag.update_id)


@supervisor.route("/add_supervisee", methods=["POST"])
@login_required
def add_supervisee():
    """
    This route handles adding a supervisee to the current supervisor. It retrieves the necessary data from the form,
    creates a new Thesis_Supervisor object, and saves it to the database.
    """
    supervisee_id = request.form.get("supervisee_id")

    # Check if the supervisee is already assigned
    existing_supervisee = Thesis_Supervisor.query.filter_by(supervisee_id=supervisee_id, supervisor_id=current_user.id).first()
    if existing_supervisee:
        return supervisee_data()
    new_supervisee = Thesis_Supervisor(
        supervisee_id=supervisee_id,
        supervisor_id=current_user.id,
        created_at=int(time.time())
    )
    db.session.add(new_supervisee)
    db.session.commit()
    return supervisee_data()


@supervisor.route("/remove_supervisee/<int:supervisee_id>")
@login_required
def remove_supervisee(supervisee_id):
    """
    This route handles removing a supervisee from the current supervisor. It retrieves the Thesis_Supervisor object,
    deletes it from the database, and redirects to the supervisee data page.
    """
    supervisee = Thesis_Supervisor.query.filter_by(supervisee_id=supervisee_id, supervisor_id=current_user.id).first()
    if supervisee:
        db.session.delete(supervisee)
        db.session.commit()

    return supervisee_data()


@supervisor.route("/delete_supervisee/<int:supervisee_id>")
@login_required
def delete_supervisee(supervisee_id):
    """
    This route handles deleting a supervisee by their ID. It retrieves the Thesis_Supervisor object,
    deletes it from the database, and redirects to the supervisee data page.
    """
    supervisee = Thesis_Supervisor.query.filter_by(id=supervisee_id).first()
    if supervisee:
        db.session.delete(supervisee)
        db.session.commit()

    return supervisee_data()


@supervisor.route("/create_thesis", methods=["POST"])
@login_required
def create_thesis():
    """
    This route handles creating a new thesis. It retrieves the necessary data from the form,
    creates a new Thesis object, and saves it to the database.
    """
    check_privileges(current_user.username, role="supervisor")
    
    title = request.form.get("title")
    description = request.form.get("description")
    level = request.form.get("level")

    new_thesis = Thesis(
        title=title,
        description=description,
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
    db.session.commit()

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/update_thesis", methods=["POST"])
@login_required
def update_thesis():
    """
    This route handles updating an existing thesis. It retrieves the necessary data from the form,
    updates the Thesis object, and saves it to the database.
    """
    thesis_id = request.form.get("thesis_id")
    title = request.form.get("title")
    description = request.form.get("description")

    thesis = Thesis.query.get_or_404(thesis_id)
    thesis.title = title
    thesis.description = description
    db.session.commit()

    return theses_data()


@supervisor.route("/delete_thesis/<int:thesis_id>")
@login_required
def delete_thesis(thesis_id):
    """
    This route handles deleting a thesis by its ID. It retrieves the Thesis object,
    deletes it from the database, and redirects to the theses data page.
    """
    check_privileges(current_user.username, role="supervisor")
    
    # Verify the thesis is supervised by the current user
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if thesis_supervisor and thesis_supervisor.thesis:
        # Delete the thesis (this will cascade to delete related records)
        db.session.delete(thesis_supervisor.thesis)
        db.session.commit()

    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/add_thesis_supervisor", methods=["POST"])
@login_required
def add_thesis_supervisor():
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")

    thesis_supervisor = Thesis_Supervisor(
        thesis_id=thesis_id,
        thesis_supervisor_id=supervisor_id,
        assigned_at=int(time.time())
    )
    db.session.add(thesis_supervisor)
    db.session.commit()

    return theses_data()


@supervisor.route("/remove_thesis_supervisor")
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


@supervisor.route("/supervisor/search", methods=["POST"])
@login_required
def search():
    """
    This route handles searching for theses or supervisees. It retrieves the search term from the form,
    performs a search in the database, and returns the results.
    """
    check_privileges(current_user.username, role="supervisor")
    
    search_term = request.form.get("search_term", "").strip()

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

    return render_template("supervisor/search_results.html", 
                         theses=theses, 
                         supervisees=supervisees,
                         search_term=search_term,
                         user_type="supervisor")


@supervisor.route("/api/thesis/<int:thesis_id>/gantt_data")
@login_required
def get_gantt_data(thesis_id):
    """
    Get Gantt chart data for a thesis including updates, todos, and status changes.
    """
    check_privileges(current_user.username, role="supervisor")
    
    # Verify the thesis is supervised by the current user
    thesis_supervisor = Thesis_Supervisor.query.filter_by(
        thesis_id=thesis_id,
        supervisor_id=current_user.id
    ).first()
    
    if not thesis_supervisor:
        return jsonify({"error": "Thesis not found or not supervised by you"}), 404
    
    thesis = Thesis.query.get(thesis_id)
    if not thesis:
        return jsonify({"error": "Thesis not found"}), 404
    
    # Get all timeline events
    events = []
    
    # Add thesis creation event
    events.append({
        "id": f"thesis_created_{thesis.id}",
        "title": f"Thesis Created: {thesis.title}",
        "start": thesis.created_at * 1000,  # Convert to milliseconds for JavaScript
        "end": thesis.created_at * 1000,
        "type": "thesis_milestone",
        "category": "Thesis",
        "description": f"Thesis '{thesis.title}' was created",
        "author": "System"
    })
    
    # Add student updates
    updates = Thesis_Update.query.filter_by(
        thesis_id=thesis_id, 
        update_type="student_update"
    ).order_by(Thesis_Update.created_at.asc()).all()
    
    for update in updates:
        author = User_mgmt.query.get(update.author_id) if update.author_id else None
        events.append({
            "id": f"update_{update.id}",
            "title": f"Student Update",
            "start": update.created_at * 1000,
            "end": update.created_at * 1000,
            "type": "student_update",
            "category": "Updates",
            "description": update.content[:100] + "..." if len(update.content) > 100 else update.content,
            "author": author.name + " " + author.surname if author else "Student"
        })
    
    # Add supervisor feedback
    feedback = Thesis_Update.query.filter_by(
        thesis_id=thesis_id, 
        update_type="supervisor_update"
    ).order_by(Thesis_Update.created_at.asc()).all()
    
    for fb in feedback:
        author = User_mgmt.query.get(fb.author_id) if fb.author_id else None
        events.append({
            "id": f"feedback_{fb.id}",
            "title": f"Supervisor Feedback",
            "start": fb.created_at * 1000,
            "end": fb.created_at * 1000,
            "type": "supervisor_feedback",
            "category": "Feedback", 
            "description": fb.content[:100] + "..." if len(fb.content) > 100 else fb.content,
            "author": author.name + " " + author.surname if author else "Supervisor"
        })
    
    # Add todos (with duration if they have due dates)
    todos = Todo.query.filter_by(thesis_id=thesis_id).order_by(Todo.created_at.asc()).all()
    
    for todo in todos:
        start_time = todo.created_at * 1000
        end_time = todo.due_date * 1000 if todo.due_date else start_time
        if todo.completed_at:
            end_time = todo.completed_at * 1000
        
        author = User_mgmt.query.get(todo.author_id) if todo.author_id else None
        assigned_to = User_mgmt.query.get(todo.assigned_to_id) if todo.assigned_to_id else None
            
        events.append({
            "id": f"todo_{todo.id}",
            "title": f"Todo: {todo.title}",
            "start": start_time,
            "end": end_time,
            "type": f"todo_{todo.status}",  # todo_pending, todo_completed, etc.
            "category": "Tasks",
            "description": todo.description or todo.title,
            "author": author.name + " " + author.surname if author else "Unknown",
            "priority": todo.priority,
            "status": todo.status,
            "assigned_to": assigned_to.name + " " + assigned_to.surname if assigned_to else None
        })
    
    # Add thesis status changes
    status_changes = Thesis_Status.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Status.updated_at.asc()).all()
    
    for status in status_changes:
        events.append({
            "id": f"status_{status.id}",
            "title": f"Status: {status.status}",
            "start": status.updated_at * 1000,
            "end": status.updated_at * 1000,
            "type": "status_change",
            "category": "Status",
            "description": f"Thesis status changed to '{status.status}'",
            "author": "System"
        })
    
    # Sort events by start time
    events.sort(key=lambda x: x["start"])
    
    # Get the student author
    thesis_author = User_mgmt.query.get(thesis.author_id) if thesis.author_id else None
    
    return jsonify({
        "thesis": {
            "id": thesis.id,
            "title": thesis.title,
            "author": thesis_author.name + " " + thesis_author.surname if thesis_author else "Unknown"
        },
        "events": events,
        "categories": ["Thesis", "Updates", "Feedback", "Tasks", "Status"]
    })


@supervisor.route("/freeze_updates", methods=["POST"])
@login_required
def freeze_updates():
    """
    This route handles freezing updates for a thesis. It retrieves the thesis ID from the form,
    sets the frozen status, and saves it to the database.
    """
    update_id = request.form.get("update_id")
    update = Thesis_Update.query.get_or_404(update_id)
    update.frozen = True
    db.session.commit()
    return thesis_detail(update.thesis_id)


@supervisor.route("/unfreeze_updates", methods=["POST"])
@login_required
def unfreeze_updates():
    """
    This route handles unfreezing updates for a thesis. It retrieves the thesis ID from the form,
    sets the frozen status to False, and saves it to the database.
    """
    update_id = request.form.get("update_id")
    update = Thesis_Update.query.get_or_404(update_id)
    update.frozen = False
    db.session.commit()
    return thesis_detail(update.thesis_id)


@supervisor.route("/freeze_thesis", methods=["POST"])
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


@supervisor.route("/unfreeze_thesis", methods=["POST"])
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


@supervisor.route("/set_advancement_status", methods=["POST"])
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


@supervisor.route("/delete_advancement_status", methods=["POST"])
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


@supervisor.route("/thesis_unfolding", methods=["POST"])
@login_required
def thesis_unfolding():
    """
    This route handles unfolding a thesis. It retrieves the thesis ID from the form,
    sets the unfolding status, and saves it to the database.
    """
    thesis_id = request.form.get("thesis_id")
    thesis = Thesis_Status.query.filter_by(thesis_id=thesis_id).order_by(db.desc(Thesis_Status.updated_at)).all()

    return theses_data("progress.html", thesis=thesis, thesis_id=thesis_id)


@supervisor.route("/freeze_objective/<int:objective_id>", methods=["POST"])
@login_required
def freeze_objective(objective_id):
    """
    This route handles freezing an objective. It retrieves the objective by ID,
    sets the frozen status to True, and saves it to the database.
    """
    check_privileges(current_user.username, role="supervisor")
    
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


@supervisor.route("/unfreeze_objective/<int:objective_id>", methods=["POST"])
@login_required
def unfreeze_objective(objective_id):
    """
    This route handles unfreezing an objective. It retrieves the objective by ID,
    sets the frozen status to False, and saves it to the database.
    """
    check_privileges(current_user.username, role="supervisor")
    
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


@supervisor.route("/freeze_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def freeze_hypothesis(hypothesis_id):
    """
    This route handles freezing a hypothesis. It retrieves the hypothesis by ID,
    sets the frozen status to True, and saves it to the database.
    """
    check_privileges(current_user.username, role="supervisor")
    
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


@supervisor.route("/unfreeze_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def unfreeze_hypothesis(hypothesis_id):
    """
    This route handles unfreezing a hypothesis. It retrieves the hypothesis by ID,
    sets the frozen status to False, and saves it to the database.
    """
    check_privileges(current_user.username, role="supervisor")
    
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


@supervisor.route("/comment_on_update", methods=["POST"])
@login_required
def comment_on_update():
    """
    This route handles adding comments to student updates. It creates a comment
    as a child update linked to the parent update.
    """
    check_privileges(current_user.username, role="supervisor")
    
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
        
        return redirect(url_for('supervisor.thesis_detail', thesis_id=parent_update.thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/tag_student_update", methods=["POST"])
@login_required
def tag_student_update():
    """
    This route handles tagging student updates. It adds tags to updates.
    """
    check_privileges(current_user.username, role="supervisor")
    
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


@supervisor.route("/set_thesis_status", methods=["POST"])
@login_required
def set_thesis_status():
    """
    This route handles setting the advancement status of a thesis. It creates or updates
    the thesis status and saves it to the database.
    """
    check_privileges(current_user.username, role="supervisor")
    
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
        
        return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


# Todo routes for supervisors
@supervisor.route("/add_todo", methods=["POST"])
@login_required
def add_todo():
    """
    Add a new todo item for a supervised thesis
    """
    check_privileges(current_user.username, role="supervisor")
    
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
        return redirect(url_for('supervisor.dashboard'))
    
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
    
    return redirect(url_for('supervisor.dashboard'))


@supervisor.route("/toggle_todo/<int:todo_id>")
@login_required
def toggle_todo(todo_id):
    """
    Toggle todo completion status
    """
    check_privileges(current_user.username, role="supervisor")
    
    # Get the todo item and verify access
    todo = Todo.query.join(Thesis_Supervisor).filter(
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


@supervisor.route("/delete_todo/<int:todo_id>")
@login_required
def delete_todo(todo_id):
    """
    Delete a todo item
    """
    check_privileges(current_user.username, role="supervisor")
    
    # Get the todo item and verify access (only author or supervisor can delete)
    todo = Todo.query.join(Thesis_Supervisor).filter(
        Todo.id == todo_id,
        (Todo.author_id == current_user.id) |  # Author can delete
        (Thesis_Supervisor.supervisor_id == current_user.id)  # Supervisor can delete
    ).first()
    
    if todo:
        db.session.delete(todo)
        db.session.commit()
    
    return redirect(url_for('supervisor.dashboard'))