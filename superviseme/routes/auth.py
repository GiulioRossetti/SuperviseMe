from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required, logout_user, login_manager, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from superviseme.models import User_mgmt
from superviseme import db
from superviseme.utils.logging_config import log_login_attempt, log_logout, log_privilege_escalation_attempt
import time

auth = Blueprint("auth", __name__)


@auth.route("/")
def index():
    """Root route that redirects to login"""
    return redirect(url_for("auth.login"))


@auth.route("/health")
def health():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "SuperviseMe"}, 200


@auth.route("/login")
def login():
    return render_template("/login.html")


@auth.route("/login", methods=["POST"])
def login_post():
    if request.method == "GET":
        return render_template("/login.html")
    # login code goes here
    email = request.form.get("email")
    password = request.form.get("password")
    remember = True if request.form.get("remember") else False

    user = User_mgmt.query.filter_by(email=email).first()

    # check if the user actually exists,
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or not check_password_hash(user.password, password):
        # Log failed login attempt
        log_login_attempt(email or 'unknown', False, request.remote_addr)
        flash("Please check your login details and try again.")
        return redirect(
            url_for("auth.login")
        )  # if the user doesn't exist or password is wrong, reload the page

    # Log successful login attempt
    log_login_attempt(user.username, True, request.remote_addr)
    
    # if the above check passes, then we know the user has the right credentials
    login_user(user, remember=remember)
    if user.user_type == "admin":
        return redirect(url_for("admin.dashboard"))
    elif user.user_type == "supervisor":
        return redirect(url_for("supervisor.dashboard"))
    elif user.user_type == "researcher":
        return redirect(url_for("researcher.dashboard"))
    else:
        return redirect(url_for("student.dashboard"))


@auth.route("/logout")
@login_required
def logout():
    # Log logout event before clearing user context
    if current_user.is_authenticated:
        log_logout(current_user.username, current_user.id)
    
    logout_user()
    print("User logged out successfully.")
    return redirect(url_for("auth.login"))


