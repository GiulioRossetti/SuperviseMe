from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, session
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from superviseme.models import User_mgmt, Thesis, Thesis_Supervisor, OrcidActivity
from superviseme import db, oauth
import datetime
import json
from flask import make_response
from superviseme.utils.orcid_client import fetch_orcid_activities
from superviseme.utils.bibtex_generator import generate_bibtex
from superviseme.utils.miscellanea import user_has_supervisor_role
from urllib.parse import urljoin

profile = Blueprint("profile", __name__)


def _dashboard_endpoint_for_user(user):
    if user.user_type == "admin":
        return "admin.dashboard"
    if user.user_type == "supervisor":
        return "supervisor.dashboard"
    if user.user_type == "researcher":
        return "researcher.dashboard"
    return "student.dashboard"


def _oauth_redirect_uri(endpoint):
    base_url = (current_app.config.get("BASE_URL") or "").strip()
    callback_path = url_for(endpoint)
    if base_url:
        return urljoin(f"{base_url.rstrip('/')}/", callback_path.lstrip("/"))
    return url_for(endpoint, _external=True)


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
                         dashboard_endpoint=_dashboard_endpoint_for_user(current_user),
                         has_supervisor_role=user_has_supervisor_role(current_user) if current_user.user_type == "researcher" else False,
                         datetime=datetime.datetime)


@profile.route("/profile/orcid")
@login_required
def orcid_publications():
    """
    Dedicated page for ORCID publication management.
    """
    orcid_activities = (
        OrcidActivity.query
        .filter_by(user_id=current_user.id)
        .order_by(OrcidActivity.publication_date.desc())
        .all()
    )
    return render_template(
        "/profile_orcid.html",
        user=current_user,
        orcid_activities=orcid_activities,
        dashboard_endpoint=_dashboard_endpoint_for_user(current_user),
        has_supervisor_role=user_has_supervisor_role(current_user) if current_user.user_type == "researcher" else False,
    )


@profile.route("/profile/orcid/connect")
@login_required
def connect_orcid():
    """
    Start OAuth flow to link ORCID to the currently authenticated account.
    """
    session["orcid_link_user_id"] = current_user.id
    session["orcid_link_next"] = "profile.orcid_publications"
    redirect_uri = _oauth_redirect_uri("auth.orcid_callback")
    return oauth.orcid.authorize_redirect(redirect_uri)


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


@profile.route("/profile/orcid/sync", methods=["POST"])
@login_required
def sync_orcid():
    """
    Sync activities from ORCID.
    """
    if not current_user.orcid_id:
        flash("Please link your ORCID account first.", "error")
        return redirect(url_for("profile.orcid_publications"))

    result = fetch_orcid_activities(current_user)

    if result["success"]:
        flash(result["message"], "success")
    else:
        flash(result["message"], "error")

    return redirect(url_for("profile.orcid_publications"))


@profile.route("/profile/orcid/export", methods=["POST"])
@login_required
def export_orcid_bibtex():
    """
    Export ORCID activities to BibTeX.
    """
    selected_ids = request.form.getlist("selected_activities")

    if request.form.get("export_type") == "all":
         activities = OrcidActivity.query.filter_by(user_id=current_user.id).order_by(OrcidActivity.publication_date.desc()).all()
    elif selected_ids:
        try:
            ids = [int(x) for x in selected_ids]
            activities = OrcidActivity.query.filter(OrcidActivity.id.in_(ids), OrcidActivity.user_id == current_user.id).all()
        except ValueError:
            flash("Invalid selection.", "error")
            return redirect(url_for("profile.orcid_publications"))
    else:
        flash("Please select items to export.", "warning")
        return redirect(url_for("profile.orcid_publications"))

    if not activities:
        flash("No publications to export.", "warning")
        return redirect(url_for("profile.orcid_publications"))

    bibtex_str = generate_bibtex(activities)

    response = make_response(bibtex_str)
    response.headers["Content-Disposition"] = "attachment; filename=publications.bib"
    response.headers["Content-Type"] = "text/plain"

    return response


# Telegram Notification Configuration Routes

@profile.route("/profile/telegram/config", methods=["GET", "POST"])
@login_required
def telegram_config():
    """
    Configure user's Telegram notification settings
    """
    if request.method == "POST":
        try:
            data = request.get_json()
            
            current_user.telegram_user_id = data.get("telegram_user_id", "").strip()
            current_user.telegram_enabled = data.get("telegram_enabled", False)
            
            # Handle notification types
            notification_types = data.get("notification_types", [])
            current_user.telegram_notification_types = json.dumps(notification_types)
            
            db.session.commit()
            
            return jsonify({
                "success": True, 
                "message": "Telegram settings saved successfully"
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "success": False, 
                "message": f"Error saving settings: {str(e)}"
            }), 500
    
    else:  # GET request
        # Parse notification types
        notification_types = []
        if current_user.telegram_notification_types:
            try:
                notification_types = json.loads(current_user.telegram_notification_types)
            except:
                notification_types = []
        
        return jsonify({
            "success": True,
            "config": {
                "telegram_user_id": current_user.telegram_user_id or "",
                "telegram_enabled": current_user.telegram_enabled,
                "notification_types": notification_types
            }
        })


@profile.route("/profile/telegram/verify", methods=["POST"])
@login_required
def verify_telegram():
    """
    Verify user's Telegram chat ID with the bot
    """
    try:
        data = request.get_json()
        telegram_user_id = data.get("telegram_user_id", "").strip()
        
        if not telegram_user_id:
            return jsonify({
                "success": False, 
                "message": "Please provide your Telegram user ID"
            }), 400
        
        from superviseme.utils.telegram_service import get_telegram_service
        service = get_telegram_service()
        # Ensure latest admin config/token is used.
        service.bot = None
        service._bot_token = None
        result = service.verify_user_chat(telegram_user_id)
        
        if result["success"]:
            # Optionally save the verified chat ID
            current_user.telegram_user_id = telegram_user_id
            db.session.commit()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False, 
            "message": f"Error verifying Telegram: {str(e)}"
        }), 500


@profile.route("/profile/telegram/test", methods=["POST"])
@login_required
def test_telegram():
    """
    Send a test notification to user's Telegram
    """
    try:
        if not current_user.telegram_enabled or not current_user.telegram_user_id:
            return jsonify({
                "success": False, 
                "message": "Telegram notifications not configured"
            }), 400
        
        from superviseme.utils.telegram_service import get_telegram_service

        service = get_telegram_service()
        # Ensure latest admin config/token is used.
        service.bot = None
        service._bot_token = None
        result = service.send_notification(
            current_user.id,
            "test",
            "Test Notification",
            "This is a test notification from SuperviseMe. If you received this, your Telegram notifications are working correctly!"
        )
        
        if result.get("success"):
            return jsonify({
                "success": True, 
                "message": "Test notification sent successfully"
            })
        else:
            return jsonify({
                "success": False, 
                "message": result.get("message", "Failed to send test notification. Please check your configuration.")
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False, 
            "message": f"Error sending test notification: {str(e)}"
        }), 500


@profile.route("/profile/telegram/bot-info")
@login_required
def telegram_bot_info():
    """
    Get current bot status/info for profile setup UI.
    """
    try:
        from superviseme.utils.telegram_service import get_telegram_service

        service = get_telegram_service()
        # Ensure latest admin config/token is used.
        service.bot = None
        service._bot_token = None
        info = service.get_bot_info()

        if not info:
            return jsonify({
                "success": False,
                "message": "Telegram bot is not configured or not reachable."
            })

        return jsonify({
            "success": True,
            "bot_info": info
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error loading bot info: {str(e)}"
        }), 500


@profile.route("/profile/telegram/notification-types")
@login_required
def get_notification_types():
    """
    Get available notification types for the user
    """
    try:
        from superviseme.utils.telegram_service import get_notification_types, get_default_notification_types
        
        all_types = get_notification_types()
        default_types = get_default_notification_types()
        
        return jsonify({
            "success": True,
            "types": all_types,
            "default_types": default_types
        })
        
    except Exception as e:
        return jsonify({
            "success": False, 
            "message": f"Error getting notification types: {str(e)}"
        }), 500
