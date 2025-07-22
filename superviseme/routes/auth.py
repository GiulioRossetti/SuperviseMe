from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required, logout_user, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from superviseme.models import User_mgmt
from superviseme import db
import time

auth = Blueprint("auth", __name__)


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
        flash("Please check your login details and try again.")
        return redirect(
            url_for("auth.login")
        )  # if the user doesn't exist or password is wrong, reload the page

    # if the above check passes, then we know the user has the right credentials
    login_user(user, remember=remember)
    if user.user_type == "admin":
        return redirect(url_for("admin.dashboard"))
    elif user.user_type == "supervisor":
        return redirect(url_for("supervisor.dashboard"))
    else:
        return redirect(url_for("student.dashboard"))


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    print("User logged out successfully.")
    return redirect(url_for("auth.login"))


