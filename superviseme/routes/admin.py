from collections import defaultdict

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import aliased
from werkzeug.security import generate_password_hash
from superviseme.models import *
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils.task_scheduler import trigger_weekly_reports_now, get_scheduler_status
from superviseme.utils.weekly_notifications import preview_weekly_supervisor_report
from superviseme import db
import datetime
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
    available_theses_by_supervisor = defaultdict(list)
    available_theses = Thesis.query.filter(Thesis.author_id.is_(None)).all()
    for supervisor in supervisors:
        available_theses_by_supervisor[supervisor].extend(
            [{"thesis": thesis} for thesis in available_theses]
        )

    return render_template("/admin/admin_dashboard.html", current_user=current_user,
                           user_counts=user_counts, thesis_counts=thesis_counts,
                           theses_by_supervisor=theses_by_supervisor, available_theses=available_theses_by_supervisor, datetime=datetime, dt=datetime.datetime.fromtimestamp, str=str)


@admin.route("/admin/users")
@login_required
def users():
    """
    This route renders the form for creating a new user. It checks if the current user has admin privileges.
    """
    check_privileges(current_user.username, role="admin")
    return render_template("/admin/users.html", current_user=current_user)


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
    user_type = request.form.get("role")

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


@admin.route("/admin/delete_user/<int:uid>", methods=["GET", "DELETE"])
@login_required
def delete_user(uid):
    """
    This route handles deleting a user. It retrieves the user by ID,
    deletes it from the database, and commits the changes.
    """
    check_privileges(current_user.username, role="admin")
    user = User_mgmt.query.filter_by(id=uid).first()
    if user:
        # Delete related thesis data if user is a student
        if user.user_type == "student":
            # Remove thesis assignments
            Thesis.query.filter_by(author_id=uid).update({"author_id": None})
        
        # Delete related supervisor assignments
        if user.user_type == "supervisor":
            Thesis_Supervisor.query.filter_by(supervisor_id=uid).delete()
        
        db.session.delete(user)
        db.session.commit()
        flash("User deleted successfully")
    else:
        flash("User not found")

    if request.method == "DELETE":
        return {"status": "success"}, 200
    
    return redirect(request.referrer)


@admin.route("/admin/update_user", methods=["POST"])
@login_required
def update_user():
    """
    This route handles updating user information.
    """
    check_privileges(current_user.username, role="admin")
    
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
    This route handles resetting a user's password to a default value.
    """
    check_privileges(current_user.username, role="admin")
    
    user = User_mgmt.query.get_or_404(user_id)
    default_password = "password123"  # Default password
    user.password = generate_password_hash(default_password, method="pbkdf2:sha256")
    
    db.session.commit()
    
    return {"status": "success", "message": f"Password reset to '{default_password}'"}, 200


@admin.route("/admin/user/<int:user_id>")
@login_required
def user_detail(user_id):
    """
    This route displays the details of a specific user including all related information.
    """
    check_privileges(current_user.username, role="admin")
    
    user = User_mgmt.query.get_or_404(user_id)
    
    # Get theses authored by this user (if student)
    authored_theses = []
    if user.user_type == "student":
        authored_theses = Thesis.query.filter_by(author_id=user_id).all()
    
    # Get theses supervised by this user (if supervisor)
    supervised_theses = []
    if user.user_type == "supervisor":
        supervised_rels = Thesis_Supervisor.query.filter_by(supervisor_id=user_id).all()
        supervised_theses = [Thesis.query.get(rel.thesis_id) for rel in supervised_rels]
    
    return render_template("/admin/user_detail.html",
                         current_user=current_user,
                         user=user,
                         authored_theses=authored_theses,
                         supervised_theses=supervised_theses,
                         datetime=datetime.datetime)


@admin.route("/admin/users_data")
@login_required
def users_data():
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

    return {
        "data": [{"id": pop.id, "name": pop.name, "surname": pop.surname, "gender": pop.gender, "user_type": pop.user_type} for pop in res],
        "total": total,
    }


@admin.route("/admin/theses")
@login_required
def theses():
    """
    This route renders the form for creating a new thesis. It checks if the current user has admin privileges.
    """
    check_privileges(current_user.username, role="admin")
    students = User_mgmt.query.filter_by(user_type="student").all()
    supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()
    return render_template("/admin/theses.html", current_user=current_user,
                           students=students, supervisors=supervisors)


@admin.route("/admin/theses_data", methods=["GET", "POST"])
@login_required
def theses_data():
    check_privileges(current_user.username, role="admin")
    
    # Handle POST request for inline editing
    if request.method == "POST":
        data = request.get_json()
        thesis_id = data.get("id")
        
        thesis = Thesis.query.get_or_404(thesis_id)
        
        if "title" in data:
            thesis.title = data["title"]
        if "level" in data:
            thesis.level = data["level"]
            
        db.session.commit()
        return {"status": "success"}, 200
    
    # Handle GET request for table data
    Author = aliased(User_mgmt)

    stmt = (
        select(Thesis, Author)
        .outerjoin(Author, Thesis.author_id == Author.id)
    )

    # search filter
    search = request.args.get("search")
    if search:
        stmt = stmt.where(
            or_(
                Author.name.ilike(f"%{search}%"),
                Thesis.level.ilike(f"%{search}%"),
                Thesis.title.ilike(f"%{search}%"),
            )
        )

    # sorting
    sort = request.args.get("sort")
    if sort:
        order = []
        for s in sort.split(","):
            direction = s[0]
            name = s[1:]
            if name not in ["title", "level", "author_cd"]:
                continue
            col = getattr(Author, name, None)
            if col is not None:
                col = col.desc() if direction == "-" else col.asc()
                order.append(col)
        if order:
            stmt = stmt.order_by(*order)

    # total count (separate execution if paginated)
    total = db.session.execute(stmt).all()
    total_count = len(total)

    # pagination
    start = request.args.get("start", type=int, default=-1)
    length = request.args.get("length", type=int, default=-1)
    if start != -1 and length != -1:
        stmt = stmt.offset(start).limit(length)

    results = db.session.execute(stmt).all()

    return {
        "total": total_count,
        "data": [
            {
                "thesis_id": thesis.id,
                "title": thesis.title,
                "level": thesis.level,
                "author_cd": author.cdl if author else None,
                "assigned": "True" if author else "False",
            }
            for thesis, author in results
        ],
    }




@admin.route("/admin/create_thesis", methods=["POST"])
@login_required
def create_thesis():
    """
    This route handles creating a new thesis. It retrieves the necessary data from the form,
    creates a new Thesis object, and saves it to the database.
    """
    check_privileges(current_user.username, role="admin")
    title = request.form.get("title")
    description = request.form.get("description")
    student_id = request.form.get("student_id")
    supervisor_id = request.form.get("supervisor_id")
    level = request.form.get("level")
    status = "thesis accepted"

    if not title or not description:
        flash("All fields are required")
        return redirect(request.referrer)

    try:
        new_thesis = Thesis(
            title=title,
            description=description,
            author_id=int(student_id) if student_id != "" else None,
            frozen=False,
            level=level,
            created_at=int(time.time()),
        )
        db.session.add(new_thesis)
        db.session.commit()

        # Only create supervisor assignment if supervisor_id is provided
        if supervisor_id and supervisor_id.strip():
            thesis_supervisor = Thesis_Supervisor(
                thesis_id=new_thesis.id,
                supervisor_id=int(supervisor_id),
                assigned_at=int(time.time()),
            )
            db.session.add(thesis_supervisor)
            db.session.commit()

        # Update the thesis status
        new_status = Thesis_Status(
            thesis_id=new_thesis.id,
            status=status,
            updated_at=int(time.time()),
        )
        db.session.add(new_status)
        db.session.commit()

        flash("Thesis created successfully")
        return redirect(url_for("admin.theses"))
    except Exception as e:
        flash(f"Error creating thesis: {e}")
        return redirect(request.referrer)


@admin.route("/admin/update_thesis", methods=["POST"])
@login_required
def update_thesis():
    """
    This route handles updating an existing thesis. It retrieves the necessary data from the form,
    updates the Thesis object, and saves it to the database.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id") or request.json.get("id")
    title = request.form.get("title") or request.json.get("title")
    level = request.form.get("level") or request.json.get("level")
    description = request.form.get("description") or request.json.get("description")

    thesis = Thesis.query.get_or_404(thesis_id)
    
    if title:
        thesis.title = title
    if level:
        thesis.level = level  
    if description:
        thesis.description = description
        
    db.session.commit()
    
    if request.is_json:
        return {"status": "success"}, 200
    
    flash("Thesis updated successfully")
    return redirect(url_for("admin.theses"))


@admin.route("/admin/delete_thesis/<int:thesis_id>", methods=["DELETE"])
@login_required
def delete_thesis(thesis_id):
    """
    This route handles deleting a thesis by its ID. It retrieves the Thesis object,
    deletes it from the database, and redirects to the theses data page.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis = Thesis.query.get_or_404(thesis_id)
    
    # Delete related records first
    Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).delete()
    Thesis_Status.query.filter_by(thesis_id=thesis_id).delete()
    Thesis_Tag.query.filter_by(thesis_id=thesis_id).delete()
    Thesis_Update.query.filter_by(thesis_id=thesis_id).delete()
    Resource.query.filter_by(thesis_id=thesis_id).delete()
    
    db.session.delete(thesis)
    db.session.commit()
    
    return {"status": "success"}, 200


@admin.route("/admin/thesis/<int:thesis_id>")
@login_required
def thesis_detail(thesis_id):
    """
    This route displays the details of a specific thesis including all related information
    like supervisors, tags, updates, and allows for editing.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis = Thesis.query.get_or_404(thesis_id)
    author = User_mgmt.query.get(thesis.author_id) if thesis.author_id else None
    supervisors_rel = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id).all()
    supervisors = [User_mgmt.query.get(rel.supervisor_id) for rel in supervisors_rel]
    status_history = Thesis_Status.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Status.updated_at.desc()).all()
    tags = Thesis_Tag.query.filter_by(thesis_id=thesis_id).all()
    updates = Thesis_Update.query.filter_by(thesis_id=thesis_id).order_by(Thesis_Update.created_at.desc()).all()
    
    # Get all students and supervisors for reassignment
    students = User_mgmt.query.filter_by(user_type="student").all()
    all_supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()
    
    return render_template("/admin/thesis_detail.html", 
                         current_user=current_user,
                         thesis=thesis,
                         author=author,
                         supervisors=supervisors,
                         status_history=status_history,
                         tags=tags,
                         updates=updates,
                         students=students,
                         all_supervisors=all_supervisors,
                         datetime=datetime.datetime)


@admin.route("/admin/assign_student", methods=["POST"])
@login_required
def assign_student():
    """
    This route handles assigning or reassigning a student to a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    student_id = request.form.get("student_id")
    
    thesis = Thesis.query.get_or_404(thesis_id)
    thesis.author_id = int(student_id) if student_id else None
    db.session.commit()
    
    flash("Student assignment updated successfully")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/assign_supervisor", methods=["POST"])
@login_required
def assign_supervisor():
    """
    This route handles assigning a supervisor to a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")
    
    # Check if this supervisor is already assigned
    existing = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id, supervisor_id=supervisor_id).first()
    if not existing:
        new_assignment = Thesis_Supervisor(
            thesis_id=thesis_id,
            supervisor_id=supervisor_id,
            assigned_at=int(time.time())
        )
        db.session.add(new_assignment)
        db.session.commit()
        flash("Supervisor assigned successfully")
    else:
        flash("Supervisor is already assigned to this thesis")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/remove_supervisor", methods=["POST"])
@login_required
def remove_supervisor():
    """
    This route handles removing a supervisor from a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    supervisor_id = request.form.get("supervisor_id")
    
    assignment = Thesis_Supervisor.query.filter_by(thesis_id=thesis_id, supervisor_id=supervisor_id).first()
    if assignment:
        db.session.delete(assignment)
        db.session.commit()
        flash("Supervisor removed successfully")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/add_thesis_tag", methods=["POST"])
@login_required
def add_thesis_tag():
    """
    This route handles adding tags to a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    tag = request.form.get("tag")
    
    if tag and thesis_id:
        # Check if tag already exists
        existing_tag = Thesis_Tag.query.filter_by(thesis_id=thesis_id, tag=tag).first()
        if not existing_tag:
            new_tag = Thesis_Tag(
                thesis_id=thesis_id,
                tag=tag
            )
            db.session.add(new_tag)
            db.session.commit()
            flash("Tag added successfully")
        else:
            flash("Tag already exists")
    
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/remove_thesis_tag", methods=["POST"])
@login_required
def remove_thesis_tag():
    """
    This route handles removing tags from a thesis.
    """
    check_privileges(current_user.username, role="admin")
    
    tag_id = request.form.get("tag_id")
    thesis_id = request.form.get("thesis_id")
    
    tag = Thesis_Tag.query.get_or_404(tag_id)
    db.session.delete(tag)
    db.session.commit()
    
    flash("Tag removed successfully")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/archive_thesis", methods=["POST"])
@login_required
def archive_thesis():
    """
    This route handles archiving/unarchiving a thesis using the frozen field.
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    action = request.form.get("action")  # "archive" or "unarchive"
    
    thesis = Thesis.query.get_or_404(thesis_id)
    thesis.frozen = (action == "archive")
    db.session.commit()
    
    status_text = "archived" if thesis.frozen else "unarchived"
    flash(f"Thesis {status_text} successfully")
    return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))


@admin.route("/admin/theses_settings")
@login_required
def theses_settings():
    """
    General Settings page for thesis management configuration.
    """
    check_privileges(current_user.username, role="admin")
    
    # Get statistics for the settings overview
    stats = {
        "total_theses": Thesis.query.count(),
        "assigned_theses": Thesis.query.filter(Thesis.author_id.isnot(None)).count(),
        "available_theses": Thesis.query.filter(Thesis.author_id.is_(None)).count(),
        "frozen_theses": Thesis.query.filter_by(frozen=True).count(),
        "thesis_levels": {
            "bachelor": Thesis.query.filter_by(level="bachelor").count(),
            "master": Thesis.query.filter_by(level="master").count(),
            "other": Thesis.query.filter_by(level="other").count()
        }
    }
    
    return render_template("/admin/theses_settings.html", 
                         current_user=current_user, 
                         stats=stats)


@admin.route("/admin/notify_settings")
@login_required  
def notify_settings():
    """
    Annotation & Notification settings page for managing communication and updates.
    """
    check_privileges(current_user.username, role="admin")
    
    # Get notification-related statistics
    stats = {
        "total_users": User_mgmt.query.count(),
        "active_supervisors": User_mgmt.query.filter_by(user_type="supervisor").count(),
        "enrolled_students": User_mgmt.query.filter_by(user_type="student").count(),
        "recent_updates": Thesis_Update.query.count() if 'Thesis_Update' in globals() else 0,
        "pending_notifications": 0  # Placeholder for future implementation
    }
    
    return render_template("/admin/notify_settings.html",
                         current_user=current_user,
                         stats=stats)


@admin.route("/admin/misc")
@login_required
def misc():
    """
    Miscellanea page for various administrative tools and utilities.
    """
    check_privileges(current_user.username, role="admin")
    
    # System information and utilities
    import os
    import datetime
    
    system_info = {
        "database_path": db.engine.url.database,
        "current_time": datetime.datetime.now(),
        "app_version": "1.0.0",  # Could be read from config
        "database_size": "N/A"  # Could be calculated based on DB type
    }
    
    # Get database file size if SQLite
    try:
        if str(db.engine.url).startswith('sqlite'):
            db_path = str(db.engine.url).replace('sqlite:///', '')
            if os.path.exists(db_path):
                size_bytes = os.path.getsize(db_path)
                # Convert to human readable format
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024:
                        system_info["database_size"] = f"{size_bytes:.1f} {unit}"
                        break
                    size_bytes /= 1024
    except Exception:
        pass
    
    # Recent activity summary
    activity_summary = {
        "recent_users": User_mgmt.query.order_by(User_mgmt.joined_on.desc()).limit(5).all(),
        "recent_theses": Thesis.query.order_by(Thesis.created_at.desc()).limit(5).all(),
        "tag_stats": {}
    }
    
    # Get popular tags
    try:
        tag_counts = db.session.query(Thesis_Tag.tag, db.func.count(Thesis_Tag.tag))\
            .group_by(Thesis_Tag.tag)\
            .order_by(db.func.count(Thesis_Tag.tag).desc())\
            .limit(10).all()
        activity_summary["tag_stats"] = {tag: count for tag, count in tag_counts}
    except Exception:
        pass
    
    return render_template("/admin/miscellanea.html",
                         current_user=current_user,
                         system_info=system_info,
                         activity_summary=activity_summary,
                         datetime=datetime.datetime,
                         dt=datetime.datetime.fromtimestamp)


@admin.route("/admin/api/system_stats")
@login_required
def system_stats():
    """
    API endpoint that returns system statistics.
    """
    check_privileges(current_user.username, role="admin")
    
    try:
        import os
        
        # Database statistics
        db_stats = {
            "total_users": User_mgmt.query.count(),
            "students": User_mgmt.query.filter_by(user_type="student").count(),
            "supervisors": User_mgmt.query.filter_by(user_type="supervisor").count(),
            "admins": User_mgmt.query.filter_by(user_type="admin").count(),
            "total_theses": Thesis.query.count(),
            "assigned_theses": Thesis.query.filter(Thesis.author_id.isnot(None)).count(),
            "available_theses": Thesis.query.filter(Thesis.author_id.is_(None)).count(),
            "frozen_theses": Thesis.query.filter_by(frozen=True).count(),
        }
        
        # System information
        system_info = {
            "database_path": str(db.engine.url.database),
            "database_size": "N/A"
        }
        
        # Get database file size if SQLite
        try:
            if str(db.engine.url).startswith('sqlite'):
                db_path = str(db.engine.url).replace('sqlite:///', '')
                if os.path.exists(db_path):
                    size_bytes = os.path.getsize(db_path)
                    # Convert to human readable format
                    for unit in ['B', 'KB', 'MB', 'GB']:
                        if size_bytes < 1024:
                            system_info["database_size"] = f"{size_bytes:.1f} {unit}"
                            break
                        size_bytes /= 1024
        except Exception:
            pass
        
        # Thesis levels distribution
        level_stats = {
            "bachelor": Thesis.query.filter_by(level="bachelor").count(),
            "master": Thesis.query.filter_by(level="master").count(),
            "other": Thesis.query.filter_by(level="other").count()
        }
        
        # Recent activity (last 30 days)
        import datetime
        thirty_days_ago = int((datetime.datetime.now() - datetime.timedelta(days=30)).timestamp())
        recent_activity = {
            "new_users": User_mgmt.query.filter(User_mgmt.joined_on >= thirty_days_ago).count(),
            "new_theses": Thesis.query.filter(Thesis.created_at >= thirty_days_ago).count(),
        }
        
        return {
            "status": "success",
            "data": {
                "database": db_stats,
                "system": system_info,
                "thesis_levels": level_stats,
                "recent_activity": recent_activity,
                "timestamp": datetime.datetime.now().isoformat()
            }
        }, 200
        
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@admin.route("/admin/api/export_data")
@login_required
def export_data():
    """
    API endpoint that exports system data as JSON.
    """
    check_privileges(current_user.username, role="admin")
    
    try:
        # Export users (excluding passwords)
        users_data = []
        users = User_mgmt.query.all()
        for user in users:
            users_data.append({
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "surname": user.surname,
                "email": user.email,
                "user_type": user.user_type,
                "cdl": user.cdl,
                "gender": user.gender,
                "nationality": user.nationality,
                "joined_on": user.joined_on
            })
        
        # Export theses
        theses_data = []
        theses = Thesis.query.all()
        for thesis in theses:
            # Get author info
            author = User_mgmt.query.get(thesis.author_id) if thesis.author_id else None
            
            # Get supervisors
            supervisors = []
            supervisor_rels = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()
            for rel in supervisor_rels:
                supervisor = User_mgmt.query.get(rel.supervisor_id)
                if supervisor:
                    supervisors.append({
                        "id": supervisor.id,
                        "name": supervisor.name,
                        "surname": supervisor.surname,
                        "email": supervisor.email
                    })
            
            # Get tags
            tags = []
            thesis_tags = Thesis_Tag.query.filter_by(thesis_id=thesis.id).all()
            for tag in thesis_tags:
                tags.append(tag.tag)
            
            # Get latest status
            latest_status = Thesis_Status.query.filter_by(thesis_id=thesis.id).order_by(Thesis_Status.updated_at.desc()).first()
            
            theses_data.append({
                "id": thesis.id,
                "title": thesis.title,
                "description": thesis.description,
                "level": thesis.level,
                "frozen": thesis.frozen,
                "created_at": thesis.created_at,
                "author": {
                    "id": author.id,
                    "name": author.name,
                    "surname": author.surname,
                    "email": author.email
                } if author else None,
                "supervisors": supervisors,
                "tags": tags,
                "status": latest_status.status if latest_status else None
            })
        
        export_data = {
            "export_info": {
                "timestamp": datetime.datetime.now().isoformat(),
                "version": "1.0.0",
                "exported_by": current_user.username
            },
            "users": users_data,
            "theses": theses_data
        }
        
        return {
            "status": "success",
            "data": export_data
        }, 200
        
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@admin.route("/admin/api/export_data/csv")
@login_required  
def export_data_csv():
    """
    API endpoint that exports system data as CSV files.
    """
    check_privileges(current_user.username, role="admin")
    
    from flask import make_response
    import csv
    import io
    import zipfile
    
    try:
        # Create in-memory zip file
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Export users CSV
            users_csv = io.StringIO()
            users_writer = csv.writer(users_csv)
            users_writer.writerow(['ID', 'Username', 'Name', 'Surname', 'Email', 'User Type', 'CDL', 'Gender', 'Nationality', 'Joined On'])
            
            users = User_mgmt.query.all()
            for user in users:
                users_writer.writerow([
                    user.id, user.username, user.name, user.surname, user.email,
                    user.user_type, user.cdl, user.gender, user.nationality, 
                    datetime.datetime.fromtimestamp(user.joined_on).isoformat() if user.joined_on else ''
                ])
            
            zip_file.writestr('users.csv', users_csv.getvalue())
            
            # Export theses CSV  
            theses_csv = io.StringIO()
            theses_writer = csv.writer(theses_csv)
            theses_writer.writerow(['ID', 'Title', 'Description', 'Level', 'Author', 'Author Email', 'Supervisors', 'Status', 'Frozen', 'Created At'])
            
            theses = Thesis.query.all()
            for thesis in theses:
                author = User_mgmt.query.get(thesis.author_id) if thesis.author_id else None
                
                # Get supervisors
                supervisors = []
                supervisor_rels = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()
                for rel in supervisor_rels:
                    supervisor = User_mgmt.query.get(rel.supervisor_id)
                    if supervisor:
                        supervisors.append(f"{supervisor.name} {supervisor.surname}")
                
                # Get latest status
                latest_status = Thesis_Status.query.filter_by(thesis_id=thesis.id).order_by(Thesis_Status.updated_at.desc()).first()
                
                theses_writer.writerow([
                    thesis.id, thesis.title, thesis.description, thesis.level,
                    f"{author.name} {author.surname}" if author else "Unassigned",
                    author.email if author else "",
                    "; ".join(supervisors),
                    latest_status.status if latest_status else "No status",
                    thesis.frozen,
                    datetime.datetime.fromtimestamp(thesis.created_at).isoformat() if thesis.created_at else ''
                ])
            
            zip_file.writestr('theses.csv', theses_csv.getvalue())
        
        zip_buffer.seek(0)
        
        response = make_response(zip_buffer.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = f'attachment; filename=superviseme_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        
        return response
        
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


# Miscellanea functionality endpoints
@admin.route("/admin/api/export_data_action", methods=["POST"])
@login_required
def export_data_action():
    """Export data in various formats"""
    check_privileges(current_user.username, role="admin")
    
    format_type = request.json.get('format', 'json')
    
    if format_type == 'csv':
        return redirect(url_for('admin.export_data_csv'))
    else:
        return redirect(url_for('admin.export_data'))


@admin.route("/admin/api/system_health", methods=["GET"])
@login_required
def system_health():
    """Check system health"""
    check_privileges(current_user.username, role="admin")
    
    try:
        health_status = {
            "database_connection": "OK",
            "user_count": User_mgmt.query.count(),
            "thesis_count": Thesis.query.count(),
            "status": "healthy"
        }
        
        return {"status": "success", "health": health_status}, 200
    except Exception as e:
        return {"status": "error", "health": {"status": "unhealthy", "error": str(e)}}, 500


@admin.route("/admin/api/generate_report", methods=["POST"])
@login_required
def generate_report():
    """Generate system report"""
    check_privileges(current_user.username, role="admin")
    
    try:
        # Get comprehensive statistics
        stats_response, _ = system_stats()
        stats_data = stats_response.get('data', {}) if isinstance(stats_response, dict) else {}
        
        report = {
            "generated_at": datetime.datetime.now().isoformat(),
            "generated_by": current_user.username,
            "summary": {
                "total_users": stats_data.get('database', {}).get('total_users', 0),
                "total_theses": stats_data.get('database', {}).get('total_theses', 0),
                "system_status": "operational"
            },
            "detailed_stats": stats_data
        }
        
        return {"status": "success", "report": report}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@admin.route("/admin/add_thesis_status", methods=["POST"])
@login_required
def add_thesis_status():
    """
    Add a new status entry to a thesis status history
    """
    check_privileges(current_user.username, role="admin")
    
    thesis_id = request.form.get("thesis_id")
    status = request.form.get("status")
    
    if not thesis_id or not status:
        flash("Both thesis ID and status are required")
        return redirect(request.referrer)
    
    try:
        new_status = Thesis_Status(
            thesis_id=int(thesis_id),
            status=status,
            updated_at=int(time.time())
        )
        db.session.add(new_status)
        db.session.commit()
        
        flash(f"Status '{status}' added successfully")
        return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))
    except Exception as e:
        flash(f"Error adding status: {e}")
        return redirect(request.referrer)


@admin.route("/admin/update_thesis_status", methods=["POST"])
@login_required
def update_thesis_status():
    """
    Update an existing thesis status entry
    """
    check_privileges(current_user.username, role="admin")
    
    status_id = request.form.get("status_id")
    new_status_value = request.form.get("status")
    
    if not status_id or not new_status_value:
        flash("Status ID and new status value are required")
        return redirect(request.referrer)
    
    try:
        status_entry = Thesis_Status.query.get_or_404(status_id)
        status_entry.status = new_status_value
        status_entry.updated_at = int(time.time())
        db.session.commit()
        
        flash(f"Status updated to '{new_status_value}' successfully")
        return redirect(url_for("admin.thesis_detail", thesis_id=status_entry.thesis_id))
    except Exception as e:
        flash(f"Error updating status: {e}")
        return redirect(request.referrer)


@admin.route("/admin/delete_thesis_status", methods=["POST"])
@login_required  
def delete_thesis_status():
    """
    Delete a thesis status entry
    """
    check_privileges(current_user.username, role="admin")
    
    status_id = request.form.get("status_id")
    
    if not status_id:
        flash("Status ID is required")
        return redirect(request.referrer)
    
    try:
        status_entry = Thesis_Status.query.get_or_404(status_id)
        thesis_id = status_entry.thesis_id
        db.session.delete(status_entry)
        db.session.commit()
        
        flash("Status deleted successfully")
        return redirect(url_for("admin.thesis_detail", thesis_id=thesis_id))
    except Exception as e:
        flash(f"Error deleting status: {e}")
        return redirect(request.referrer)


# Email Notification Management Routes

@admin.route("/admin/notifications")
@login_required
def notifications():
    """
    This route displays the email notification management page
    """
    check_privileges(current_user.username, role="admin")
    
    # Get scheduler status
    scheduler_status = get_scheduler_status()
    
    # Get all supervisors for testing
    supervisors = User_mgmt.query.filter_by(user_type="supervisor").all()
    
    return render_template("admin/notifications.html", 
                         scheduler_status=scheduler_status,
                         supervisors=supervisors)


@admin.route("/admin/notifications/trigger", methods=["POST"])
@login_required
def trigger_notifications():
    """
    Manually trigger weekly supervisor reports
    """
    check_privileges(current_user.username, role="admin")
    
    try:
        results = trigger_weekly_reports_now()
        flash(f"Weekly reports triggered successfully. Sent: {results.get('emails_sent', 0)}, Failed: {results.get('emails_failed', 0)}")
    except Exception as e:
        flash(f"Error triggering weekly reports: {str(e)}")
    
    return redirect(url_for("admin.notifications"))


@admin.route("/admin/notifications/preview/<int:supervisor_id>")
@login_required
def preview_notification(supervisor_id):
    """
    Preview the weekly notification for a specific supervisor
    """
    check_privileges(current_user.username, role="admin")
    
    try:
        preview_data = preview_weekly_supervisor_report(supervisor_id)
        
        if 'error' in preview_data:
            return jsonify({'error': preview_data['error']}), 400
        
        return jsonify(preview_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@admin.route("/admin/search", methods=["POST"])
@login_required
def search():
    """
    Handle search requests from admin interface.
    Search across users and theses.
    """
    check_privileges(current_user.username, role="admin")
    
    search_term = request.form.get("search_term", "").strip()
    
    # Search for users
    users = []
    if search_term:
        users = User_mgmt.query.filter(
            or_(
                User_mgmt.name.ilike(f"%{search_term}%"),
                User_mgmt.surname.ilike(f"%{search_term}%"),
                User_mgmt.username.ilike(f"%{search_term}%"),
                User_mgmt.email.ilike(f"%{search_term}%"),
                User_mgmt.cdl.ilike(f"%{search_term}%")
            )
        ).all()
    
    # Search for theses
    theses = []
    if search_term:
        theses = Thesis.query.filter(
            or_(
                Thesis.title.ilike(f"%{search_term}%"),
                Thesis.description.ilike(f"%{search_term}%"),
                Thesis.level.ilike(f"%{search_term}%")
            )
        ).all()
    
    return render_template("admin/search_results.html", 
                         users=users, 
                         theses=theses, 
                         search_term=search_term,
                         user_type="admin")


@admin.route("/admin/notifications/status")
@login_required
def notification_status():
    """
    Get the current status of the notification scheduler
    """
    check_privileges(current_user.username, role="admin")
    
    try:
        status = get_scheduler_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Telegram Bot Configuration Routes

@admin.route("/admin/telegram/config", methods=["GET", "POST"])
@login_required
def telegram_config():
    """
    Configure Telegram bot settings
    """
    check_privileges(current_user.username, role="admin")
    
    if request.method == "POST":
        try:
            data = request.get_json()
            
            # Get or create Telegram bot config
            config = TelegramBotConfig.query.filter_by(is_active=True).first()
            if not config:
                config = TelegramBotConfig(
                    bot_token="",
                    bot_username="",
                    notification_types="[]",
                    created_at=int(time.time()),
                    updated_at=int(time.time())
                )
                db.session.add(config)
            
            # Update configuration
            config.bot_token = data.get("bot_token", "")
            config.bot_username = data.get("bot_username", "")
            config.webhook_url = data.get("webhook_url", "")
            config.is_active = data.get("is_active", True)
            config.notification_types = data.get("notification_types", "[]")
            config.frequency_settings = data.get("frequency_settings", "{}")
            config.updated_at = int(time.time())
            
            db.session.commit()
            
            return jsonify({"success": True, "message": "Telegram configuration saved successfully"})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "message": f"Error saving configuration: {str(e)}"}), 500
    
    else:  # GET request
        config = TelegramBotConfig.query.filter_by(is_active=True).first()
        if config:
            return jsonify({
                "success": True,
                "config": {
                    "bot_token": config.bot_token[:10] + "..." if len(config.bot_token) > 10 else "",
                    "bot_username": config.bot_username,
                    "webhook_url": config.webhook_url,
                    "is_active": config.is_active,
                    "notification_types": config.notification_types,
                    "frequency_settings": config.frequency_settings
                }
            })
        else:
            return jsonify({
                "success": True,
                "config": {
                    "bot_token": "",
                    "bot_username": "",
                    "webhook_url": "",
                    "is_active": False,
                    "notification_types": "[]",
                    "frequency_settings": "{}"
                }
            })


@admin.route("/admin/telegram/test", methods=["POST"])
@login_required
def test_telegram_bot():
    """
    Test Telegram bot connection
    """
    check_privileges(current_user.username, role="admin")
    
    try:
        from superviseme.utils.telegram_service import get_telegram_service
        service = get_telegram_service()
        # Clear cached config to reload from database
        service._config = None
        service.bot = None
        result = service.test_bot_connection()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"Error testing bot: {str(e)}"}), 500


@admin.route("/admin/telegram/notification-types")
@login_required
def get_telegram_notification_types():
    """
    Get available Telegram notification types
    """
    check_privileges(current_user.username, role="admin")
    
    try:
        from superviseme.utils.telegram_service import get_notification_types
        types = get_notification_types()
        return jsonify({"success": True, "types": types})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error getting notification types: {str(e)}"}), 500

