"""Admin: backup and restore of the database and the uploaded files."""
import os
import tempfile

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required, logout_user

from superviseme.routes.admin import admin, _audit_admin_action
from superviseme.utils import backup as bk
from superviseme.utils.miscellanea import check_privileges


def _gate():
    gate = check_privileges(current_user.username, role="admin")
    return None if gate is True else gate


@admin.route("/admin/backup")
@login_required
def backup_page():
    gate = _gate()
    if gate is not None:
        return gate
    from datetime import datetime
    auto = (os.environ.get("BACKUP_AUTO") or "").strip().lower() in ("1", "true", "yes", "on")
    return render_template("admin/backup.html", current_user=current_user, backups=bk.list_backups(), auto=auto,
                           keep=int(os.environ.get("BACKUP_KEEP", "7") or 7), directory=bk.backup_dir(),
                           revision=bk.schema_revision(), fmt=lambda ts: datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M UTC"))


@admin.route("/admin/backup/create", methods=["POST"])
@login_required
def backup_create():
    gate = _gate()
    if gate is not None:
        return gate
    try:
        name = bk.create_backup("manual", note=(request.form.get("note") or "").strip())
    except Exception:
        from flask import current_app
        current_app.logger.exception("Backup failed")
        flash("The backup could not be created")
        return redirect(url_for("admin.backup_page"))
    _audit_admin_action("backup_create", "backup", name)
    flash("Backup created")
    return redirect(url_for("admin.backup_page"))


@admin.route("/admin/backup/<name>/download")
@login_required
def backup_download(name):
    gate = _gate()
    if gate is not None:
        return gate
    try:
        path = bk.backup_path(name)
    except bk.BackupError:
        abort(404)
    _audit_admin_action("backup_download", "backup", name)
    return send_file(path, mimetype="application/zip", as_attachment=True, download_name=name)


@admin.route("/admin/backup/<name>/delete", methods=["POST"])
@login_required
def backup_delete(name):
    gate = _gate()
    if gate is not None:
        return gate
    try:
        os.unlink(bk.backup_path(name))
    except bk.BackupError:
        abort(404)
    _audit_admin_action("backup_delete", "backup", name)
    flash("Backup deleted")
    return redirect(url_for("admin.backup_page"))


@admin.route("/admin/backup/restore", methods=["POST"])
@login_required
def backup_restore():
    """Restore from a listed backup (``name``) or an uploaded zip (``file``); needs the typed confirmation RESTORE."""
    gate = _gate()
    if gate is not None:
        return gate
    if (request.form.get("confirm") or "").strip() != "RESTORE":
        flash("Type RESTORE to confirm: the current data will be replaced")
        return redirect(url_for("admin.backup_page"))
    tmp = None
    try:
        upload = request.files.get("file")
        if upload and upload.filename:
            fd, tmp = tempfile.mkstemp(suffix=".zip", dir=bk.backup_dir())
            os.close(fd)
            upload.save(tmp)
            path, label = tmp, "uploaded file"
        else:
            path = bk.backup_path(request.form.get("name") or "")
            label = request.form["name"]
        result = bk.restore_backup(path)
    except bk.BackupError as exc:
        flash(str(exc))
        return redirect(url_for("admin.backup_page"))
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    # the restored data may not contain the current session's user: sign in again
    try:
        _audit_admin_action("backup_restore", "backup", label, details=result)
    except Exception:
        pass
    logout_user()
    flash("Backup restored. Please sign in again.")
    return redirect(url_for("auth.login"))
