from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, and_
from werkzeug.security import generate_password_hash
from superviseme.utils import security
from superviseme.models import *
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils.logging_config import log_security_event
from superviseme import db
import datetime
import time

admin = Blueprint("admin", __name__)


def _audit_admin_action(action, target_type, target_id=None, status="success", details=None):
    log_security_event(
        "admin_high_risk_action",
        details={
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "status": status,
            "details": details or {},
        },
        user_id=current_user.id if current_user.is_authenticated else None,
    )


@admin.route("/admin/dashboard")
@login_required
def dashboard():
    """
    This route is for admin data. It retrieves all users from the database
    and renders them in a template.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check

    # count all users by their user_type
    user_counts = {
        "students": User_mgmt.query.filter_by(user_type="student").count(),
        "supervisors": User_mgmt.query.filter_by(user_type="supervisor").count(),
        "researchers": User_mgmt.query.filter_by(user_type="researcher").count(),
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
        theses_by_supervisor[supervisor] = [
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
    theses_by_supervisor = {
        supervisor: [t for t in theses if t["student"] is not None]
        for supervisor, theses in theses_by_supervisor.items()
    }

    # for each supervisor get the list of available theses not assigned to students
    available_theses = [{"thesis": thesis} for thesis in Thesis.query.filter(Thesis.author_id.is_(None)).all()]

    from superviseme.routes.admin_research import research_stats
    return render_template("/admin/admin_dashboard.html", current_user=current_user, research=research_stats(),
                           user_counts=user_counts, thesis_counts=thesis_counts,
                           theses_by_supervisor=theses_by_supervisor,
                           workload=sorted(theses_by_supervisor.items(), key=lambda kv: (-len(kv[1]), (kv[0].surname or '').lower())),
                           available_theses=available_theses, supervisors=supervisors,
                           greeting=__import__("superviseme.utils.dashboard_data", fromlist=["greeting_key"]).greeting_key(), datetime=datetime, dt=datetime.datetime.fromtimestamp, str=str)


@admin.route("/admin/users")
@login_required
def users():
    """
    This route renders the form for creating a new user. It checks if the current user has admin privileges.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    counts = dict(db.session.query(User_mgmt.user_type, db.func.count(User_mgmt.id)).group_by(User_mgmt.user_type).all())
    disabled_count = User_mgmt.query.filter(User_mgmt.is_enabled.is_(False)).count()
    return render_template("/admin/users.html", current_user=current_user, total_users=sum(counts.values()),
                           counts=counts, disabled_count=disabled_count)


def _like_escape(term):
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@admin.route("/admin/users/cards")
@login_required
def users_cards():
    """Server-side paginated and filtered user cards (HTML fragment) for the users board."""
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    query = User_mgmt.query
    for term in (request.args.get("q") or "").split():
        like = f"%{_like_escape(term)}%"
        query = query.filter(db.or_(
            User_mgmt.name.ilike(like, escape="\\"), User_mgmt.surname.ilike(like, escape="\\"),
            User_mgmt.email.ilike(like, escape="\\"), User_mgmt.username.ilike(like, escape="\\"),
        ))
    role = request.args.get("role")
    if role in ("student", "supervisor", "researcher", "admin"):
        query = query.filter(User_mgmt.user_type == role)
    status = request.args.get("status")
    if status in ("0", "1"):
        query = query.filter(User_mgmt.is_enabled.is_(status == "1"))
    per = max(1, min(request.args.get("per", 8, type=int), 48))
    total = query.count()
    pages = max(1, -(-total // per))
    page = max(1, min(request.args.get("page", 1, type=int), pages))
    users = query.order_by(User_mgmt.surname, User_mgmt.name, User_mgmt.id).offset((page - 1) * per).limit(per).all()
    sup_researchers = {r[0] for r in db.session.query(Supervisor_Role.researcher_id).filter(Supervisor_Role.active.is_(True)).all()}
    html = render_template("/admin/components/user_cards.html", users=users, sup_researchers=sup_researchers,
                           datetime=__import__("datetime").datetime)
    return jsonify(total=total, page=page, pages=pages, per=per, html=html)


@admin.route("/admin/create_user", methods=["POST"])
@login_required
def create_user():
    """
    This route handles creating a new student. It retrieves the necessary data from the form,
    creates a new User_mgmt object, and saves it to the database.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
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
    user_type = request.form.get("role")

    user = User_mgmt.query.filter_by(email=email).first()

    if user:
        flash("Email address already exists")
        return redirect(request.referrer)

    if password != password2:
        flash("Passwords do not match")
        return redirect(request.referrer)

    pw_error = security.validate_password(password)
    if pw_error:
        flash(pw_error)
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


@admin.route("/admin/delete_user/<int:uid>", methods=["DELETE"])
@login_required
def delete_user(uid):
    """
    This route handles deleting a user. It retrieves the user by ID,
    deletes it from the database, and commits the changes.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    user = User_mgmt.query.filter_by(id=uid).first()
    if user:
        deleted_username = user.username
        deleted_user_type = user.user_type
        # Delete related thesis data if user is a student
        if user.user_type == "student":
            # Remove thesis assignments
            Thesis.query.filter_by(author_id=uid).update({"author_id": None})
        
        # Delete related supervisor assignments
        if user.user_type == "supervisor":
            Thesis_Supervisor.query.filter_by(supervisor_id=uid).delete()
        
        from superviseme.models import Calendar_Feed
        Calendar_Feed.query.filter_by(user_id=uid).delete()
        from superviseme.utils.research_output import delete_links_for
        delete_links_for(user_id=uid)
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully")
        _audit_admin_action(
            action="delete_user",
            target_type="user",
            target_id=uid,
            status="success",
            details={"username": deleted_username, "user_type": deleted_user_type},
        )
    else:
        flash("User not found")
        _audit_admin_action(
            action="delete_user",
            target_type="user",
            target_id=uid,
            status="not_found",
        )

    return {"status": "success"}, 200


@admin.route("/admin/update_user", methods=["POST"])
@login_required
def update_user():
    """
    This route handles updating user information.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    user_id = request.form.get("user_id")
    name = request.form.get("name")
    surname = request.form.get("surname")
    email = request.form.get("email")
    username = request.form.get("username")
    user_type = request.form.get("user_type")
    gender = request.form.get("gender")
    nationality = request.form.get("nationality")
    cdl = request.form.get("cdl")
    
    user = User_mgmt.query.get_or_404(user_id)
    if "max_students" in request.form:
        raw_max = (request.form.get("max_students") or "").strip()
        if raw_max and not (raw_max.isdigit() and int(raw_max) <= 100):
            flash("The maximum number of students must be between 0 and 100.")
            return redirect(url_for("admin.user_detail", user_id=user_id))
        user.max_students = int(raw_max) if raw_max else None

    # Check if email or username is already taken by another user
    if email != user.email:
        existing_email = User_mgmt.query.filter_by(email=email).filter(User_mgmt.id != user_id).first()
        if existing_email:
            flash("Email address already exists")
            return redirect(url_for("admin.user_detail", user_id=user_id))
    
    if username != user.username:
        existing_username = User_mgmt.query.filter_by(username=username).filter(User_mgmt.id != user_id).first()
        if existing_username:
            flash("Username already exists")
            return redirect(url_for("admin.user_detail", user_id=user_id))
    
    # Update user fields
    user.name = name
    user.surname = surname
    user.email = email
    user.username = username
    user.user_type = user_type
    user.gender = gender or None
    user.nationality = nationality or None
    user.cdl = cdl or None
    
    db.session.commit()
    flash("User updated successfully")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin.route("/admin/reset_user_password/<int:user_id>", methods=["POST"])
@login_required
def reset_user_password(user_id):
    """
    This route handles resetting a user's password to an admin-provided value.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    user = User_mgmt.query.get_or_404(user_id)
    payload = request.get_json(silent=True) or {}
    new_password = request.form.get("new_password") or payload.get("new_password")
    if not new_password or len(new_password) < 12 or security.validate_password(new_password):
        return {
            "status": "error",
            "message": "new_password is required and must be at least 12 characters long.",
        }, 400

    user.password = generate_password_hash(new_password, method="pbkdf2:sha256")
    
    db.session.commit()
    _audit_admin_action(
        action="reset_user_password",
        target_type="user",
        target_id=user_id,
        status="success",
    )
    
    return {"status": "success", "message": "Password reset successfully."}, 200


@admin.route("/admin/user/<int:user_id>")
@login_required
def user_detail(user_id):
    """
    This route displays the details of a specific user including all related information.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    user = User_mgmt.query.get_or_404(user_id)
    from superviseme.utils.privacy import log_profile_view
    log_profile_view(current_user, user)
    researcher_supervisor_role = None
    if user.user_type == "researcher":
        researcher_supervisor_role = Supervisor_Role.query.filter_by(
            researcher_id=user_id, active=True
        ).first()
    
    # Get theses authored by this user (if student)
    authored_theses = []
    if user.user_type == "student":
        authored_theses = Thesis.query.filter_by(author_id=user_id).all()
    
    # Get theses supervised by this user (if supervisor)
    supervised_theses = []
    if user.user_type == "supervisor":
        supervised_theses = (
            Thesis.query.join(Thesis_Supervisor)
            .filter(Thesis_Supervisor.supervisor_id == user_id)
            .all()
        )
    
    from superviseme.utils.thesis_board import build_thesis_cards
    thesis_cards, _archived = build_thesis_cards(authored_theses + supervised_theses)
    thesis_cards = thesis_cards + _archived
    recent_updates = Thesis_Update.query.filter_by(author_id=user_id).order_by(Thesis_Update.created_at.desc()).limit(6).all()
    projects = ResearchProject.query.filter_by(researcher_id=user_id).order_by(ResearchProject.created_at.desc()).all() \
        if user.user_type == "researcher" else []
    from superviseme.utils.research_output import linked_outputs
    return render_template("/admin/user_detail.html",
                         current_user=current_user, linked_outputs=linked_outputs(user_id=user_id),
                         thesis_cards=thesis_cards, recent_updates=recent_updates, projects=projects,
                         dt=datetime.datetime.fromtimestamp,
                         user=user,
                         researcher_supervisor_role=researcher_supervisor_role,
                         authored_theses=authored_theses,
                         supervised_theses=supervised_theses,
                         datetime=datetime.datetime)


@admin.route("/admin/users_data", methods=["GET", "POST"])
@login_required
def users_data():
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    if request.method == "POST":
        data = request.get_json()
        user_id = data.get("id")
        if user_id:
            user = User_mgmt.query.get_or_404(user_id)

            if "name" in data: user.name = data["name"]
            if "surname" in data: user.surname = data["surname"]
            if "gender" in data: user.gender = data["gender"]
            if "user_type" in data: user.user_type = data["user_type"]
            if "is_enabled" in data: user.is_enabled = bool(data["is_enabled"])

            db.session.commit()
            return {"status": "success"}, 200

    query = User_mgmt.query

    # search filter
    search = request.args.get("search")
    if search:
        query = query.filter(
            db.or_(
                User_mgmt.name.like(f"%{search}%"),
            )
        )
    total = query.count()

    # sorting
    sort = request.args.get("sort")
    if sort:
        order = []
        for s in sort.split(","):
            direction = s[0]
            name = s[1:]
            if name not in ["name", "surname", "gender", "user_type"]:
                name = "name"
            col = getattr(User_mgmt, name)
            if direction == "-":
                col = col.desc()
            order.append(col)
        if order:
            query = query.order_by(*order)

    # pagination
    start = request.args.get("start", type=int, default=-1)
    length = request.args.get("length", type=int, default=-1)
    if start != -1 and length != -1:
        query = query.offset(start).limit(length)

    # response
    res = query.all()
    researcher_ids = [u.id for u in res if u.user_type == "researcher"]
    active_supervisor_researcher_ids = set()
    if researcher_ids:
        active_supervisor_researcher_ids = {
            row[0]
            for row in db.session.query(Supervisor_Role.researcher_id)
            .filter(
                Supervisor_Role.researcher_id.in_(researcher_ids),
                Supervisor_Role.active.is_(True),
            )
            .all()
        }

    return {
        "data": [{
            "id": pop.id,
            "name": pop.name,
            "surname": pop.surname,
            "gender": pop.gender,
            "user_type": pop.user_type,
            "is_enabled": pop.is_enabled,
            "google_id": pop.google_id,
            "orcid_id": pop.orcid_id,
            "has_supervisor_privileges": pop.id in active_supervisor_researcher_ids,
        } for pop in res],
        "total": total,
    }


@admin.route("/admin/grant_supervisor_role", methods=["POST"])
@login_required
def grant_supervisor_role():
    """
    This route handles granting supervisor role to a researcher.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check

    researcher_id = request.form.get("researcher_id")
    
    if not researcher_id:
        flash("Researcher ID is required")
        return redirect(request.referrer)

    researcher = db.session.get(User_mgmt, researcher_id)
    if not researcher or researcher.user_type != "researcher":
        flash("Researcher not found or invalid user type")
        return redirect(request.referrer)

    # Check if already has supervisor role
    existing_role = Supervisor_Role.query.filter_by(
        researcher_id=researcher_id, active=True
    ).first()
    
    if existing_role:
        flash("This researcher already has supervisor privileges")
        return redirect(request.referrer)

    try:
        supervisor_role = Supervisor_Role(
            researcher_id=researcher_id,
            granted_by=current_user.id,
            granted_at=int(time.time()),
            active=True,
            created_at=int(time.time()),
            updated_at=int(time.time()),
        )
        db.session.add(supervisor_role)
        db.session.commit()

        flash(f"Supervisor role granted to {researcher.name} {researcher.surname}")
        return redirect(request.referrer)
    except Exception as e:
        flash(f"Error granting supervisor role: {e}")
        return redirect(request.referrer)


@admin.route("/admin/revoke_supervisor_role", methods=["POST"]) 
@login_required
def revoke_supervisor_role():
    """
    This route handles revoking supervisor role from a researcher.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check

    researcher_id = request.form.get("researcher_id")
    
    if not researcher_id:
        flash("Researcher ID is required")
        return redirect(request.referrer)

    try:
        supervisor_role = Supervisor_Role.query.filter_by(
            researcher_id=researcher_id, active=True
        ).first()
        
        if supervisor_role:
            supervisor_role.active = False
            supervisor_role.updated_at = int(time.time())
            db.session.commit()
            
            researcher = db.session.get(User_mgmt, researcher_id)
            flash(f"Supervisor role revoked from {researcher.name} {researcher.surname}")
        else:
            flash("No active supervisor role found for this researcher")
        
        return redirect(request.referrer)
    except Exception as e:
        flash(f"Error revoking supervisor role: {e}")
        return redirect(request.referrer)


# Domain modules register their routes on the same blueprint (and are re-exported for shared views).
from superviseme.routes.admin_theses import *  # noqa: E402,F401,F403
from superviseme.routes.admin_system import *  # noqa: E402,F401,F403
from superviseme.routes.admin_research import *  # noqa: E402,F401,F403
from superviseme.routes.admin_backup import *  # noqa: E402,F401,F403
