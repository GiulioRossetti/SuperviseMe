from flask import Blueprint, request, render_template, redirect, url_for
from flask_login import login_required, current_user
from superviseme.utils.miscellanea import check_privileges
from superviseme.models import *
from superviseme import db
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
    else:
        thesis_stats = {
            'updates_count': 0,
            'supervisor_comments': 0,
            'resources_count': 0,
        }
        recent_updates = []
        
    return render_template("student/student_dashboard.html", 
                         thesis=thesis, 
                         thesis_stats=thesis_stats,
                         recent_updates=recent_updates)


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
    
    # Get all updates for this thesis (both student and supervisor updates)
    updates = Thesis_Update.query.filter_by(thesis_id=thesis.id).order_by(Thesis_Update.created_at.desc()).all()
    
    # Get resources
    resources = Resource.query.filter_by(thesis_id=thesis.id).all()
    
    return render_template("student/thesis.html", thesis=thesis, supervisors=supervisors,
                           tags=tags, updates=updates, resources=resources)


@student.route("/post_update", methods=["POST"])
@login_required
def post_update():
    """
    This route handles posting updates to a thesis. It retrieves the necessary data from the form,
    creates a new Update object, and saves it to the database.
    """
    check_privileges(current_user.username, role="student")
    
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

    return redirect(url_for('student.thesis_data'))


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
    check_privileges(current_user.username, role="student")
    
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