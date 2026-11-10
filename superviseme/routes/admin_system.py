"""Admin: system tools, exports, notifications, search, Telegram.
"""
from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from superviseme.models import *
from superviseme.utils.miscellanea import check_privileges
from superviseme.utils.task_scheduler import trigger_weekly_reports_now, get_scheduler_status
from superviseme.utils.weekly_notifications import preview_weekly_supervisor_report
from superviseme import db
import datetime

from superviseme.routes.admin import admin


@admin.route("/admin/notify_settings")
@login_required  
def notify_settings():
    """
    Annotation & Notification settings page for managing communication and updates.
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
            author = db.session.get(User_mgmt, thesis.author_id) if thesis.author_id else None
            
            # Get supervisors
            supervisors = []
            supervisor_rels = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()
            for rel in supervisor_rels:
                supervisor = db.session.get(User_mgmt, rel.supervisor_id)
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
                author = db.session.get(User_mgmt, thesis.author_id) if thesis.author_id else None
                
                # Get supervisors
                supervisors = []
                supervisor_rels = Thesis_Supervisor.query.filter_by(thesis_id=thesis.id).all()
                for rel in supervisor_rels:
                    supervisor = db.session.get(User_mgmt, rel.supervisor_id)
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    format_type = request.json.get('format', 'json')
    
    if format_type == 'csv':
        return redirect(url_for('admin.export_data_csv'))
    else:
        return redirect(url_for('admin.export_data'))


@admin.route("/admin/api/system_health", methods=["GET"])
@login_required
def system_health():
    """Check system health"""
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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


# Email Notification Management Routes

@admin.route("/admin/notifications")
@login_required
def notifications():
    """
    This route displays the email notification management page
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    search_term = request.form.get("search_term", "").strip()
    
    # Validate search term
    if not search_term:
        # If no search term, redirect back to dashboard with message
        from flask import flash, redirect, url_for
        flash("Please enter a search term.", "warning")
        return redirect(url_for('admin.dashboard'))
    
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
                         user_type="admin",
                         dt=datetime.datetime.fromtimestamp)


@admin.route("/admin/notifications/status")
@login_required
def notification_status():
    """
    Get the current status of the notification scheduler
    """
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    if request.method == "POST":
        try:
            data = request.get_json(silent=True) or {}
            
            # Get or create Telegram bot config
            config = TelegramBotConfig.query.filter_by(is_active=True).first()
            if not config:
                config = TelegramBotConfig(
                    bot_token="",
                    bot_username="",
                    notification_types="[]"
                )
                db.session.add(config)
            
            # Update configuration
            config.bot_token = data.get("bot_token", "")
            config.bot_username = data.get("bot_username", "")
            config.webhook_url = data.get("webhook_url", "")
            config.is_active = data.get("is_active", True)
            config.notification_types = data.get("notification_types", "[]")
            config.frequency_settings = data.get("frequency_settings", "{}")
            
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
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
    privilege_check = check_privileges(current_user.username, role="admin")
    if privilege_check is not True:
        return privilege_check
    
    try:
        from superviseme.utils.telegram_service import get_notification_types
        types = get_notification_types()
        return jsonify({"success": True, "types": types})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error getting notification types: {str(e)}"}), 500
