from flask import Blueprint, request, render_template, abort, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import  select, and_, func
from superviseme.utils.miscellanea import check_privileges
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

    return render_template("/supervisor/supervisor_dashboard.html", current_user=current_user,
                           user_counts=user_counts, thesis_counts=thesis_counts,
                           theses_by_supervisor=theses_by_supervisor, available_theses=available_theses_by_supervisor, dt=datetime.fromtimestamp, str=str)

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
    for ts in thesis_supervisors:
        if ts.thesis and ts.thesis.author:
            supervisees.append({
                'student': ts.thesis.author,
                'thesis': ts.thesis
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
    return render_template("supervisor/theses.html", theses=theses)


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

    return render_template("supervisor/thesis_detail.html", thesis=thesis, updates=updates,
                           supervisors=supervisors, author=author,
                           thesis_tags=thesis_tags, resources=resources)


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
    update = Thesis_Update.query.get_or_404(update_id)
    db.session.delete(update)
    db.session.commit()

    return thesis_detail(update.thesis_id)


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
    comment_id = request.form.get("comment_id")
    comment = Thesis_Update.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()

    return thesis_detail(comment.thesis_id)


@supervisor.route("/modify_update", methods=["POST"])
@login_required
def modify_update():
    """
    This route handles modifying an update. It retrieves the necessary data from the form,
    updates the content of the update in the database, and redirects to the thesis detail page.
    """
    update_id = request.form.get("update_id")
    new_content = request.form.get("new_content")

    update = Thesis_Update.query.get_or_404(update_id)
    update.content = new_content
    db.session.commit()

    return thesis_detail(update.thesis_id)


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
    thesis = Thesis.query.get_or_404(thesis_id)
    db.session.delete(thesis)
    db.session.commit()

    return theses_data()


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


@supervisor.route("/search", methods=["POST"])
@login_required
def search():
    """
    This route handles searching for theses or supervisees. It retrieves the search term from the form,
    performs a search in the database, and returns the results.
    """
    search_term = request.form.get("search_term")

    # Search for theses
    theses = Thesis.query.filter(Thesis.title.ilike(f"%{search_term}%")).all()

    # Search for supervisees
    supervisees = User_mgmt.query.filter(User_mgmt.username.ilike(f"%{search_term}%")).all()

    return render_template("search_results.html", theses=theses, supervisees=supervisees)


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