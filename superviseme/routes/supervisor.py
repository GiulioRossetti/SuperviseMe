from flask import Blueprint, request, render_template, abort, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from sqlalchemy import select, and_, func, or_
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils.activity_tracker import get_inactive_students
from superviseme.models import *
from superviseme import db
from datetime import datetime
from werkzeug.security import generate_password_hash
import time

supervisor = Blueprint("supervisor", __name__)


@supervisor.route("/supervisor/dashboard")
@login_required
def dashboard():
    """
    This route is for admin data. It retrieves all users from the database
    and renders them in a template.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check

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
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Get students through thesis supervision relationship
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    active_supervisees = []
    past_supervisees = []
    
    # Get inactive students data
    inactive_data = get_inactive_students(current_user.id)
    inactive_dict = {data['student'].id: data for data in inactive_data}
    
    for ts in thesis_supervisors:
        if ts.thesis and ts.thesis.author:
            student_data = inactive_dict.get(ts.thesis.author.id, {})
            
            supervisee_info = {
                'student': ts.thesis.author,
                'thesis': ts.thesis,
                'is_inactive': student_data.get('is_inactive', False),
                'days_inactive': student_data.get('days_inactive'),
                'last_activity_location': student_data.get('last_activity_location')
            }
            
            # Separate active and archived/frozen theses
            if ts.thesis.frozen:
                past_supervisees.append(supervisee_info)
            else:
                active_supervisees.append(supervisee_info)
    
    # Fix "Inactive for None days" issue by providing a default value
    for supervisee in active_supervisees + past_supervisees:
        if supervisee['days_inactive'] is None:
            supervisee['days_inactive'] = 'Unknown'
    
    return render_template("supervisor/supervisees.html", 
                         supervisees=active_supervisees, 
                         past_supervisees=past_supervisees)


@supervisor.route("/theses")
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
    thesis_supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    theses = [ts.thesis for ts in thesis_supervisors]
    return render_template("supervisor/theses.html", theses=theses, dt=datetime.fromtimestamp)


@supervisor.route("/thesis/<thesis_id>")
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
                           dt=datetime.fromtimestamp)


@supervisor.route("/supervisor/post_update", methods=["POST"])
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

    # Parse and create todo references
    from superviseme.utils.todo_parser import parse_todo_references, create_todo_references
    todo_refs = parse_todo_references(content)
    if todo_refs:
        create_todo_references(new_update.id, todo_refs)

    # Create notification for student
    from superviseme.utils.notifications import create_supervisor_feedback_notification
    create_supervisor_feedback_notification(thesis_id, current_user.id, content)

    return thesis_detail(thesis_id)


@supervisor.route("/supervisor/post_comment", methods=["POST"])
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


@supervisor.route("/supervisor/delete_update/<int:update_id>")
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
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
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


@supervisor.route("/supervisor/modify_update", methods=["POST"])
@login_required
def modify_update():
    """
    This route handles modifying an update. It retrieves the necessary data from the form,
    updates the content of the update in the database, and redirects to the thesis detail page.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
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


@supervisor.route("/supervisor/modify_comment", methods=["POST"])
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


@supervisor.route("/supervisor/tag_update", methods=["POST"])
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
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    search_term = request.form.get("search_term", "").strip()

    # Validate search term
    if not search_term:
        # If no search term, redirect back to dashboard with message
        from flask import flash, redirect, url_for
        flash("Please enter a search term.", "warning")
        return redirect(url_for('supervisor.supervisor_dashboard'))

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


@supervisor.route("/unfreeze_objective/<int:objective_id>", methods=["POST"])
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


@supervisor.route("/freeze_hypothesis/<int:hypothesis_id>", methods=["POST"])
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


@supervisor.route("/unfreeze_hypothesis/<int:hypothesis_id>", methods=["POST"])
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


@supervisor.route("/comment_on_update", methods=["POST"])
@login_required
def comment_on_update():
    """
    This route handles adding comments to student updates. It creates a comment
    as a child update linked to the parent update.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
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
        
        return redirect(url_for('supervisor.thesis_detail', thesis_id=parent_update.thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/tag_student_update", methods=["POST"])
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


@supervisor.route("/set_thesis_status", methods=["POST"])
@login_required
def set_thesis_status():
    """
    This route handles setting the advancement status of a thesis. It creates or updates
    the thesis status and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
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
        
        return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))
    
    return redirect(url_for('supervisor.theses_data'))


# Todo routes for supervisors
@supervisor.route("/supervisor/add_todo", methods=["POST"])
@login_required
def add_todo():
    """
    Add a new todo item for a supervised thesis
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
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
    
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


@supervisor.route("/supervisor/toggle_todo/<int:todo_id>")
@login_required
def toggle_todo(todo_id):
    """
    Toggle todo completion status
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
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


@supervisor.route("/supervisor/delete_todo/<int:todo_id>")
@login_required
def delete_todo(todo_id):
    """
    Delete a todo item
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
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


# Student management routes for supervisors
@supervisor.route("/create_student", methods=["POST"])
@login_required
def create_student():
    """
    This route allows supervisors to create new student accounts.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    email = request.form.get("email")
    username = request.form.get("username")
    name = request.form.get("name")
    surname = request.form.get("surname")
    cdl = request.form.get("cdl")
    gender = request.form.get("gender")
    nationality = request.form.get("nationality")
    password = request.form.get("password")
    password2 = request.form.get("password2")

    # Validation
    if User_mgmt.query.filter_by(email=email).first():
        flash("Email address already exists")
        return redirect(request.referrer)

    if User_mgmt.query.filter_by(username=username).first():
        flash("Username already exists")
        return redirect(request.referrer)

    if password != password2:
        flash("Passwords do not match")
        return redirect(request.referrer)

    # Create new student
    new_student = User_mgmt(
        email=email,
        username=username,
        password=generate_password_hash(password, method="pbkdf2:sha256"),
        name=name,
        surname=surname,
        cdl=cdl,
        nationality=nationality,
        gender=gender,
        user_type="student",
        joined_on=int(time.time()),
    )
    
    db.session.add(new_student)
    db.session.commit()
    flash(f"Student {name} {surname} created successfully")
    
    return redirect(url_for('supervisor.supervisee_data'))


@supervisor.route("/edit_student/<int:student_id>", methods=["POST"])
@login_required
def edit_student(student_id):
    """
    This route allows supervisors to edit student accounts they supervise.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this student
    student = User_mgmt.query.join(Thesis, Thesis.author_id == User_mgmt.id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        User_mgmt.id == student_id,
        User_mgmt.user_type == "student",
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not student:
        flash("Student not found or not supervised by you")
        return redirect(url_for('supervisor.supervisee_data'))
    
    # Update student information
    student.name = request.form.get("name", student.name)
    student.surname = request.form.get("surname", student.surname)
    student.email = request.form.get("email", student.email)
    student.cdl = request.form.get("cdl", student.cdl)
    student.gender = request.form.get("gender", student.gender)
    student.nationality = request.form.get("nationality", student.nationality)
    
    # Only update password if provided
    new_password = request.form.get("password")
    if new_password:
        password2 = request.form.get("password2")
        if new_password != password2:
            flash("Passwords do not match")
            return redirect(request.referrer)
        student.password = generate_password_hash(new_password, method="pbkdf2:sha256")
    
    db.session.commit()
    flash(f"Student {student.name} {student.surname} updated successfully")
    
    return redirect(url_for('supervisor.supervisee_data'))


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


@supervisor.route("/delete_student/<int:student_id>", methods=["POST", "DELETE"])
@login_required
def delete_student(student_id):
    """
    This route allows supervisors to delete student accounts they supervise.
    Only students with no active thesis assignments can be deleted.
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this student
    student = User_mgmt.query.join(Thesis, Thesis.author_id == User_mgmt.id).join(
        Thesis_Supervisor, Thesis_Supervisor.thesis_id == Thesis.id
    ).filter(
        User_mgmt.id == student_id,
        User_mgmt.user_type == "student",
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not student:
        flash("Student not found or not supervised by you")
        return redirect(url_for('supervisor.supervisee_data'))
    
    # Check if student has any active theses (only allow deletion if no active theses)
    active_theses = Thesis.query.filter_by(author_id=student_id, frozen=False).count()
    if active_theses > 0:
        flash(f"Cannot delete student {student.name} {student.surname}. Student has active thesis assignments.")
        return redirect(url_for('supervisor.supervisee_data'))
    
    # Remove thesis assignments (set author_id to None for completed/frozen theses)
    Thesis.query.filter_by(author_id=student_id).update({"author_id": None})
    
    # Delete the student
    db.session.delete(student)
    db.session.commit()
    flash(f"Student {student.name} {student.surname} deleted successfully")
    
    return redirect(url_for('supervisor.supervisee_data'))


@supervisor.route("/assign_thesis", methods=["POST"])
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
    thesis = Thesis.query.get(thesis_id)
    if thesis.author_id:
        flash("Thesis is already assigned to a student")
        return redirect(url_for('supervisor.theses_data'))
    
    # Assign thesis to student
    thesis.author_id = student_id
    db.session.commit()
    flash(f"Thesis '{thesis.title}' assigned to {student.name} {student.surname}")
    
    return redirect(url_for('supervisor.theses_data'))


@supervisor.route("/unassign_thesis/<int:thesis_id>", methods=["POST"])
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
    
    thesis = Thesis.query.get(thesis_id)
    student_name = ""
    if thesis.author_id:
        student = User_mgmt.query.get(thesis.author_id)
        student_name = f"{student.name} {student.surname}" if student else ""
    
    # Unassign thesis
    thesis.author_id = None
    db.session.commit()
    flash(f"Thesis '{thesis.title}' unassigned from {student_name}")
    
    return redirect(url_for('supervisor.theses_data'))


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
    privilege_check = check_privileges(current_user.username, role="supervisor")
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
        return redirect(url_for('supervisor.dashboard'))
    
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
    
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


@supervisor.route("/edit_objective/<int:objective_id>", methods=["POST"])
@login_required
def edit_objective(objective_id):
    """
    Allow supervisors to edit objectives in supervised theses
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this objective
    objective = Thesis_Objective.query.join(Thesis_Supervisor).filter(
        Thesis_Objective.id == objective_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not objective:
        flash("Objective not found or not accessible")
        return redirect(url_for('supervisor.dashboard'))
    
    objective.title = request.form.get("title", objective.title)
    objective.description = request.form.get("description", objective.description)
    
    db.session.commit()
    flash("Objective updated successfully")
    
    return redirect(url_for('supervisor.thesis_detail', thesis_id=objective.thesis_id))


@supervisor.route("/supervisor/add_hypothesis", methods=["POST"])
@login_required
def add_hypothesis():
    """
    Allow supervisors to add hypotheses to supervised theses
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
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
        return redirect(url_for('supervisor.dashboard'))
    
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
    
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


@supervisor.route("/edit_hypothesis/<int:hypothesis_id>", methods=["POST"])
@login_required
def edit_hypothesis(hypothesis_id):
    """
    Allow supervisors to edit hypotheses in supervised theses
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
    if privilege_check is not True:
        return privilege_check
    
    # Verify supervisor has access to this hypothesis
    hypothesis = Thesis_Hypothesis.query.join(Thesis_Supervisor).filter(
        Thesis_Hypothesis.id == hypothesis_id,
        Thesis_Supervisor.supervisor_id == current_user.id
    ).first()
    
    if not hypothesis:
        flash("Hypothesis not found or not accessible")
        return redirect(url_for('supervisor.dashboard'))
    
    hypothesis.title = request.form.get("title", hypothesis.title)
    hypothesis.description = request.form.get("description", hypothesis.description)
    
    db.session.commit()
    flash("Hypothesis updated successfully")
    
    return redirect(url_for('supervisor.thesis_detail', thesis_id=hypothesis.thesis_id))


# Meeting Notes routes for supervisors
@supervisor.route("/supervisor/add_meeting_note", methods=["POST"])
@login_required
def add_meeting_note():
    """
    Allow supervisors to add meeting notes to supervised theses
    """
    privilege_check = check_privileges(current_user.username, role="supervisor")
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
        return redirect(url_for('supervisor.dashboard'))
    
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
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))


@supervisor.route("/supervisor/edit_meeting_note/<int:note_id>", methods=["POST"])
@login_required
def edit_meeting_note(note_id):
    """
    Allow supervisors to edit meeting notes in supervised theses
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
    return redirect(url_for('supervisor.thesis_detail', thesis_id=meeting_note.thesis_id))


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
    
    thesis_id = meeting_note.thesis_id
    db.session.delete(meeting_note)
    db.session.commit()
    
    flash("Meeting note deleted successfully")
    return redirect(url_for('supervisor.thesis_detail', thesis_id=thesis_id))