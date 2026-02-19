from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required, logout_user, login_manager, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from superviseme.models import User_mgmt
from superviseme import db, oauth
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

    if not user.is_enabled:
        log_login_attempt(user.username, False, request.remote_addr, details="User disabled")
        flash("Your account is pending approval. Please wait for an admin to enable it.")
        return redirect(url_for("auth.login"))

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


@auth.route('/login/google')
def google_login():
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth.route('/login/google/callback')
def google_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
             user_info = oauth.google.userinfo()
    except Exception as e:
        flash(f"Error logging in with Google: {e}")
        return redirect(url_for("auth.login"))

    email = user_info.get('email')
    google_id = user_info.get('sub')
    name = user_info.get('given_name', '')
    surname = user_info.get('family_name', '')
    picture = user_info.get('picture')

    # Try to find user by google_id or email
    user = User_mgmt.query.filter(or_(User_mgmt.google_id == google_id, User_mgmt.email == email)).first()

    if not user:
        # Create new user
        # Generate a random password since it won't be used
        import secrets
        password = secrets.token_urlsafe(16)

        # Check if username exists (email as username or part of email)
        username = email.split('@')[0]
        if User_mgmt.query.filter_by(username=username).first():
            username = f"{username}_{secrets.token_hex(4)}"

        new_user = User_mgmt(
            email=email,
            username=username,
            name=name,
            surname=surname,
            password=generate_password_hash(password, method="pbkdf2:sha256"),
            user_type="student", # Default to student
            joined_on=int(time.time()),
            google_id=google_id,
            is_enabled=False, # Disabled by default for Google signup
            profile_pic=picture
        )
        db.session.add(new_user)
        db.session.commit()
        flash("Account created via Google. Please wait for admin approval.")
        return redirect(url_for("auth.login"))

    else:
        # Update google_id if missing (e.g. existing user logging in with Google for first time)
        if not user.google_id:
            user.google_id = google_id
            if picture:
                user.profile_pic = picture
            db.session.commit()

        # Check if enabled
        if not user.is_enabled:
            log_login_attempt(user.username, False, request.remote_addr, details="User disabled (Google Login)")
            flash("Your account is pending approval. Please wait for an admin to enable it.")
            return redirect(url_for("auth.login"))

        # Log in
        log_login_attempt(user.username, True, request.remote_addr, details="Google Login")
        login_user(user, remember=True)

        # Redirect based on role (same logic as login_post)
        if user.user_type == "admin":
            return redirect(url_for("admin.dashboard"))
        elif user.user_type == "supervisor":
            return redirect(url_for("supervisor.dashboard"))
        elif user.user_type == "researcher":
            return redirect(url_for("researcher.dashboard"))
        else:
            return redirect(url_for("student.dashboard"))
