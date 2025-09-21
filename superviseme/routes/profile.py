from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from superviseme.models import User_mgmt, Thesis, Thesis_Supervisor
from superviseme import db
import datetime

profile = Blueprint("profile", __name__)


@profile.route("/profile")
@login_required
def profile_page():
    """
    Profile page for the current logged in user with CRUD operations.
    """
    # Get user's theses based on user type
    authored_theses = []
    supervised_theses = []
    
    if current_user.user_type == "student":
        authored_theses = Thesis.query.filter_by(author_id=current_user.id).all()
    elif current_user.user_type == "supervisor":
        supervised_rels = Thesis_Supervisor.query.filter_by(supervisor_id=current_user.id).all()
        supervised_theses = [Thesis.query.get(rel.thesis_id) for rel in supervised_rels if Thesis.query.get(rel.thesis_id)]
    
    return render_template("/profile.html",
                         user=current_user,
                         authored_theses=authored_theses,
                         supervised_theses=supervised_theses,
                         datetime=datetime.datetime)


@profile.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    """
    Update current user's profile information.
    """
    name = request.form.get("name")
    surname = request.form.get("surname")
    email = request.form.get("email")
    nationality = request.form.get("nationality")
    cdl = request.form.get("cdl")
    gender = request.form.get("gender")
    
    # Check if email is already taken by another user
    if email != current_user.email:
        existing_email = User_mgmt.query.filter_by(email=email).filter(User_mgmt.id != current_user.id).first()
        if existing_email:
            flash("Email address already exists", "error")
            return redirect(url_for("profile.profile_page"))
    
    # Update user fields
    current_user.name = name
    current_user.surname = surname
    current_user.email = email
    current_user.nationality = nationality or None
    current_user.cdl = cdl or None
    current_user.gender = gender or None
    
    db.session.commit()
    flash("Profile updated successfully", "success")
    return redirect(url_for("profile.profile_page"))


@profile.route("/profile/change_password", methods=["POST"])
@login_required
def change_password():
    """
    Change current user's password.
    """
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    # Verify current password
    if not check_password_hash(current_user.password, current_password):
        flash("Current password is incorrect", "error")
        return redirect(url_for("profile.profile_page"))
    
    # Verify new passwords match
    if new_password != confirm_password:
        flash("New passwords do not match", "error")
        return redirect(url_for("profile.profile_page"))
    
    # Update password
    current_user.password = generate_password_hash(new_password, method="pbkdf2:sha256")
    db.session.commit()
    
    flash("Password changed successfully", "success")
    return redirect(url_for("profile.profile_page"))