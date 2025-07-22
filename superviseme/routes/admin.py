from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from superviseme.models import *
from superviseme.utils.miscellanea import check_privileges
from superviseme import db
import time

admin = Blueprint("admin", __name__)


@admin.route("/admin/dashboard")
@login_required
def dashboard():
    """
    This route is for admin data. It retrieves all users from the database
    and renders them in a template.
    """
    check_privileges(current_user.username, role="admin")

    # count all users by their user_type
    user_counts = {
        "students": User_mgmt.query.filter_by(user_type="student").count(),
        "supervisors": User_mgmt.query.filter_by(user_type="supervisor").count(),
        "admins": User_mgmt.query.filter_by(user_type="admin").count(),
    }

    # count all theses by their status
    thesis_counts = {
        "total": Thesis.query.count(),
    }

    supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()

    # for each supervisor get list of theses assigned to them along with the name of the student
    theses_by_supervisor = {}
    for supervisor in supervisors:
        theses = Thesis_Supervisor.query.filter_by(supervisor_id=supervisor.id).all()
        theses_by_supervisor[supervisor.username] = [
            {"thesis": Thesis.query.filter_by(id=thesis.id), "student": User_mgmt.query.get(thesis.student_id).surname} for thesis in theses
        ]

    return render_template("/admin/admin_dashboard.html", current_user=current_user,
                           user_counts=user_counts, thesis_counts=thesis_counts,
                           theses_by_supervisor=theses_by_supervisor)


@admin.route("/admin/new_user")
@login_required
def new_user():
    """
    This route renders the form for creating a new user. It checks if the current user has admin privileges.
    """
    check_privileges(current_user.username, role="admin")
    return render_template("/admin/create_user.html", current_user=current_user)


@admin.route("/admin/create_user", methods=["POST"])
@login_required
def create_user():
    """
    This route handles creating a new student. It retrieves the necessary data from the form,
    creates a new User_mgmt object, and saves it to the database.
    """
    check_privileges(current_user.username, role="admin")
    email = request.form.get("email")
    username = request.form.get("username")
    name = request.form.get("name")
    surname = request.form.get("surname")
    cdl = request.form.get("cdl")
    gender = request.form.get("gender")
    nationality = request.form.get("nationality")
    password = request.form.get("password")
    password2 = request.form.get("password2")
    user_type = request.form.get("type")

    user = User_mgmt.query.filter_by(email=email).first()

    if user:
        flash("Email address already exists")
        return redirect(request.referrer)

    if password != password2:
        flash("Passwords do not match")
        return redirect(request.referrer)

    # create a new user with the form data. Hash the password so the plaintext version isn't saved.
    new_user = User_mgmt(
        email=email,
        username=username,
        password=generate_password_hash(password, method="pbkdf2:sha256"),
        name=name,
        surname=surname,
        cdl=cdl,
        nationality=nationality,
        gender=gender,
        user_type=user_type,
        joined_on=int(time.time()),
    )
    db.session.add(new_user)
    db.session.commit()
    return dashboard()


@admin.route("/admin/delete_user/<int:uid>")
@login_required
def delete_user(uid):
    """
    This route handles deleting a student. It retrieves the user by ID,
    deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="admin")
    user = User_mgmt.query.filter_by(id=uid).first()
    if user:
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully")
    else:
        flash("User not found")

    return redirect(request.referrer)


