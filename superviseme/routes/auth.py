from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from superviseme.models import User_mgmt
from superviseme import db
import time

auth = Blueprint("auth", __name__)


@auth.route("/signup")
def signup():
    return render_template("register.html")


@auth.route("/signup", methods=["POST"])
def signup_post():
    # code to validate and add user to database goes here

    email = request.form.get("email")
    name = request.form.get("name")
    password = request.form.get("password")

    user = User_mgmt.query.filter_by(email=email).first()

    if (
        user
    ):  # if a user is found, we want to redirect back to signup page so user can try again
        flash("Email address already exists")
        return redirect(url_for("auth.signup_post"))

    # create a new user with the form data. Hash the password so the plaintext version isn't saved.
    new_user = User_mgmt(
        email=email,
        username=name,
        password=generate_password_hash(password, method="pbkdf2:sha256"),
        role="student",
        joined_on=int(time.time()),
    )
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for("main.feeed_logged"))


@auth.route("/login")
def login():
    return render_template("login.html")


@auth.route("/login", methods=["POST"])
def login_post():
    if request.method == "GET":
        return render_template("login.html")
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
   # try:
    login_user(user, remember=remember)
    if user.user_type == "admin":
        return redirect(url_for("admin.dashboard"))
    elif user.user_type == "supervisor":
        return redirect(url_for("supervisor.dashboard"))
    else:
        return redirect(url_for("student.dashboard"))
   # except:
   #     flash("Please check your login details and try again.")
   #     return redirect(url_for("auth.login"))


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return render_template("login.html")
