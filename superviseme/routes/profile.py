from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from superviseme.models import User_mgmt, Thesis, Thesis_Supervisor
from superviseme import db
import datetime
import json

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
        
        from superviseme.utils.telegram_service import send_telegram_notification
        
        success = send_telegram_notification(
            current_user.id,
            "test",
            "Test Notification",
            "This is a test notification from SuperviseMe. If you received this, your Telegram notifications are working correctly!"
        )
        
        if success:
            return jsonify({
                "success": True, 
                "message": "Test notification sent successfully"
            })
        else:
            return jsonify({
                "success": False, 
                "message": "Failed to send test notification. Please check your configuration."
            }), 500
            
    except Exception as e:
        return jsonify({
            "success": False, 
            "message": f"Error sending test notification: {str(e)}"
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