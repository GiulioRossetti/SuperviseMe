from flask import Blueprint, request, render_template
from flask_login import login_required, current_user
from superviseme.models import *
from superviseme import db
import time

student = Blueprint("student", __name__)


@student.route("/student")
@login_required
def student_data():
    """
    This route is for student data. It retrieves all students from the database
    and renders them in a template.
    """
    students = User_mgmt.query.filter_by(id=current_user.id).first()
    return render_template("student.html", student=student)


@student.route("/thesis")
@login_required
def thesis_data():
    """
    This route is for thesis data. It retrieves all thesis entries from the database
    and renders them in a template.
    """
    theses = Thesis.query.filter_by(user_id=current_user.id).first()
    supervisors = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
    tags = Thesis_Tag.query.filter_by(thesis_id=current_user.id).all()
    updates = Thesis_Update.query.filter_by(author_id=current_user.id).order_by(Thesis_Update.update_id).all()
    resources = Resource.query.filter_by(thesis_id=current_user.id).all()
    return render_template("thesis.html", theses=theses, supervisors=supervisors,
                           tags=tags, updates=updates, resources=resources)


@student.route("/post_update", methods=["POST"])
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
        update_type="update",
        created_at=int(time.time())
    )

    db.session.add(new_update)
    db.session.commit()

    return thesis_data()


@student.route("/post_comment", methods=["POST"])
@login_required
def post_comment():
    """
    This route handles posting comments on updates. It retrieves the necessary data from the form,
    creates a new Update object with the comment, and saves it to the database.
    """
    update_id = request.form.get("update_id")
    content = request.form.get("content")
    thesis_id = request.form.get("thesis_id")

    new_comment = Thesis_Update(
        thesis_id=thesis_id,  # No thesis associated with comments
        author_id=current_user.id,
        content=content,
        update_type="comment",
        parent_id=update_id,  # Link to the original update
        created_at=int(time.time())
    )

    db.session.add(new_comment)
    db.session.commit()

    return thesis_data()


@student.route("/delete_update/<int:update_id>")
@login_required
def delete_update(update_id):
    """
    This route handles deleting an update. It retrieves the update by its ID,
    deletes it from the database, and commits the changes.
    """
    update = Thesis_Update.query.filter_by(id=update_id).first()
    if update:
        db.session.delete(update)
        db.session.commit()

    return thesis_data()


@student.route("/delete_comment/<int:comment_id>")
@login_required
def delete_comment(comment_id):
    """
    This route handles deleting a comment. It retrieves the comment by its ID,
    deletes it from the database, and commits the changes.
    """
    comment = Thesis_Update.query.filter_by(id=comment_id).first()
    if comment:
        db.session.delete(comment)
        db.session.commit()

    return thesis_data()


@student.route("/modify_comment", methods=["POST"])
@login_required
def modify_comment():
    """
    This route handles modifying a comment. It retrieves the necessary data from the form,
    updates the comment in the database, and commits the changes.
    """
    comment_id = request.form.get("comment_id")
    new_content = request.form.get("new_content")

    comment = Thesis_Update.query.filter_by(id=comment_id).first()
    if comment:
        comment.content = new_content
        db.session.commit()

    return thesis_data()


@student.route("/modify_update", methods=["POST"])
@login_required
def modify_update():
    """
    This route handles modifying an update. It retrieves the necessary data from the form,
    updates the update in the database, and commits the changes.
    """
    update_id = request.form.get("update_id")
    new_content = request.form.get("new_content")

    update = Thesis_Update.query.filter_by(id=update_id).first()
    if update:
        update.content = new_content
        db.session.commit()

    return thesis_data()


@student.route("/tag_update", methods=["POST"])
@login_required
def tag_update():
    """
    This route handles tagging an update. It retrieves the necessary data from the form,
    creates a new Update_Tag object, and saves it to the database.
    """
    update_id = request.form.get("update_id")
    tag = request.form.get("tag")

    new_tag = Update_Tag(
        update_id=update_id,
        tag=tag
    )

    db.session.add(new_tag)
    db.session.commit()

    return thesis_data()


@student.route("/remove_update_tag", methods=["POST"])
@login_required
def remove_update_tag():
    """
    This route handles removing a tag from an update. It retrieves the necessary data from the form,
    finds the Update_Tag object, deletes it from the database, and commits the changes.
    """
    update_id = request.form.get("update_id")
    tag = request.form.get("tag")

    update_tag = Update_Tag.query.filter_by(update_id=update_id, tag=tag).first()
    if update_tag:
        db.session.delete(update_tag)
        db.session.commit()

    return thesis_data()


@student.route("/add_resource", methods=["POST"])
@login_required
def add_resource():
    """
    This route handles adding a resource to a thesis. It retrieves the necessary data from the form,
    creates a new Resource object, and saves it to the database.
    """
    thesis_id = request.form.get("thesis_id")
    resource_type = request.form.get("resource_type")
    resource_link = request.form.get("resource_link")
    description = request.form.get("description")

    new_resource = Resource(
        thesis_id=thesis_id,
        resource_type=resource_type,
        resource_link=resource_link,
        description=description,
        created_at=int(time.time())
    )

    db.session.add(new_resource)
    db.session.commit()

    return thesis_data()


@student.route("/delete_resource/<int:resource_id>")
@login_required
def delete_resource(resource_id):
    """
    This route handles deleting a resource. It retrieves the resource by its ID,
    deletes it from the database, and commits the changes.
    """
    resource = Resource.query.filter_by(id=resource_id).first()
    if resource:
        db.session.delete(resource)
        db.session.commit()

    return thesis_data()